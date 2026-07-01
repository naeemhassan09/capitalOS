# CapitalOS — Backup & Recovery

CapitalOS holds your entire financial history in one PostgreSQL database. This
document describes the provided backup/restore tooling, the consequences of
losing your encryption key, and how to bring the system back up on a fresh VPS.

> **Status:** the scripts in `deploy/scripts/` are provided and documented for
> production use. **Scheduling** (cron/systemd) and **off-site upload** are left
> to the operator — see [Deferred](#deferred).

The scripts run **from the host** and use `docker compose exec` to reach the
`postgres` service, so run them on the machine where the stack is deployed (they
use `docker-compose.yml` by default; override with `COMPOSE_FILE=`).

---

## What gets backed up

- **The database** — a logical `pg_dump` of the `POSTGRES_DB` database, taken
  with `--clean --if-exists --no-owner --no-privileges` so it restores cleanly
  over an existing schema. This includes every account, transaction, goal,
  reserve, holding, exchange rate, category, rule, session and audit row.

- **NOT automatically included (back these up separately):**
  - **`.env`**, especially **`SECRET_KEY`** and **`ENCRYPTION_KEY`** (see the
    key-loss section below).
  - **`BACKUP_ENCRYPTION_PASSPHRASE`** if you encrypt backups.
  - Uploaded CSVs in the `uploads` volume (regenerable from source statements).

---

## `backup.sh` — create a backup

```bash
make backup
# or, directly:
BACKUP_ENCRYPTION_PASSPHRASE='…' deploy/scripts/backup.sh
```

What it does:

1. Streams `pg_dump` out of the `postgres` service and pipes it through
   `gzip -9`.
2. If `BACKUP_ENCRYPTION_PASSPHRASE` is set, the compressed stream is encrypted
   with **OpenSSL AES-256-CBC** (`-pbkdf2 -salt`) and written as
   `capitalos-<db>-<UTC-timestamp>.sql.gz.enc`. If unset, it is written
   unencrypted as `….sql.gz` (and the script logs that encryption is disabled).
3. Verifies the output is non-trivially sized (guards against a silently failed
   dump).
4. **Prunes** old backups on a grandfather-father-son schedule:
   **7 daily, 4 weekly, 6 monthly** — the newest file in each bucket is kept,
   everything else is deleted. Files are matched by the UTC timestamp embedded
   in their name.

Output goes to `BACKUP_DIR` (default `./backups`, which is gitignored). Nothing
large is ever written unencrypted to disk — the encrypt/compress happens in the
pipe.

---

## `restore.sh` — restore a backup

```bash
make restore f=backups/capitalos-capitalos-20260701T030000Z.sql.gz.enc
# or, directly:
BACKUP_ENCRYPTION_PASSPHRASE='…' deploy/scripts/restore.sh <file>
```

What it does:

1. Detects the file type by extension (`.sql.gz.enc`, `.sql.gz`, or `.sql`) and
   builds the matching decode pipeline: `openssl -d` → `gzip -d` → `psql`.
   Encrypted files require `BACKUP_ENCRYPTION_PASSPHRASE`.
2. **Prompts for confirmation** — you must type the target database name to
   proceed, because restore is destructive (the dump drops and recreates
   objects). Set `FORCE=1` to skip the prompt in automation.
3. Streams the decoded SQL into `psql` with `ON_ERROR_STOP=1`, so any failed
   statement aborts the restore loudly.

Restore into an alternate database with `TARGET_DB=<name>` (this is how
verification uses a throwaway DB).

---

## `verify-backup.sh` — prove a backup is restorable

```bash
deploy/scripts/verify-backup.sh backups/capitalos-...sql.gz.enc
```

The classic backup failure is discovering, at recovery time, that months of
backups were never restorable. This script guards against that:

1. Creates a **throwaway** database `capitalos_verify_<timestamp>`.
2. Restores the backup into it (via `restore.sh` with `FORCE=1` and
   `TARGET_DB=`).
3. Runs a **sanity count** on a core table (`VERIFY_TABLE`, default `users`) and
   reports the row count. An empty core table is flagged as a warning.
4. **Always drops** the throwaway database, even on failure (trap on exit).

Run it periodically (e.g. weekly) against your most recent backup.

---

## Lost encryption key — consequences

`ENCRYPTION_KEY` (Fernet) encrypts **application-level fields** — account IBANs
and TOTP secrets — before they are written to the database. Therefore:

- **The database dump alone is not enough to fully recover those fields.** If you
  restore a dump but no longer have the `ENCRYPTION_KEY` that was in effect when
  the data was written, the encrypted columns are **permanently unreadable**
  (there is no recovery path — that is the point of encryption).
- The rest of the data (balances, transactions, goals, reserves, holdings, FX
  rates) is **not** field-encrypted and restores normally regardless of the key.
- `SECRET_KEY` signs session cookies. Losing/rotating it invalidates existing
  sessions (users must log in again) but does not lose data.

**Mitigation — back up your keys separately from your database:**

- Store `ENCRYPTION_KEY` (and `SECRET_KEY`, and `BACKUP_ENCRYPTION_PASSPHRASE`)
  in a password manager or an offline secrets vault — **not** in the same place
  as the database dumps.
- If backups are encrypted, losing `BACKUP_ENCRYPTION_PASSPHRASE` makes the
  `.sql.gz.enc` files themselves undecryptable — treat it with the same care.
- When you rotate `ENCRYPTION_KEY`, you must re-encrypt existing fields under the
  new key before discarding the old one (no automated rotation is provided —
  see Deferred).

---

## Restore on a new VPS (outline)

1. **Provision** a host with Docker + the Compose plugin. Clone the repo (or copy
   `docker-compose.yml`, the `deploy/` directory, and `.env.example`).
2. **Restore secrets first.** Recreate `.env` from your separate secrets backup,
   ensuring **the same `ENCRYPTION_KEY`** as the source system (and
   `BACKUP_ENCRYPTION_PASSPHRASE` if backups are encrypted). Set production
   values: strong `SECRET_KEY`/`POSTGRES_PASSWORD`, `APP_ENV=production`,
   `SESSION_COOKIE_SECURE=true`, and your real `DOMAIN`.
3. **Start Postgres only**, so the database exists before restoring:
   `docker compose up -d postgres`.
4. **Copy the backup file** to the host (e.g. into `./backups/`).
5. **Restore:** `deploy/scripts/restore.sh backups/<file>` and confirm the db
   name when prompted. (Migrations are already baked into the dump; you do not
   need to run `alembic upgrade` before restoring a full dump.)
6. **Bring up the rest of the stack:** `docker compose up -d`. The backend
   container runs `alembic upgrade head` on start, which is a no-op if the dump
   is current.
7. **Verify:** log in as the owner, confirm accounts/balances, and check that
   True Deployable Capital matches expectations. If IBANs display, your
   `ENCRYPTION_KEY` matches; if they are blank/undecryptable, the key differs.
8. **Point DNS** at the new host; Caddy will obtain HTTPS certificates for
   `DOMAIN` automatically.

---

## Deferred

- **Scheduling** — no cron/systemd timer is shipped; wire `make backup` into your
  scheduler of choice.
- **Off-site / object-storage upload** — `BACKUP_S3_ENDPOINT` / `BACKUP_S3_BUCKET`
  settings are reserved but not used by the scripts; upload the produced files to
  off-site storage yourself.
- **Automated key rotation** and **PITR / WAL archiving** — not provided; the
  tooling here is logical (`pg_dump`) point-in-snapshot backup only.
