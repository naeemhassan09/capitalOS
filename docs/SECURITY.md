# CapitalOS — Security Model

CapitalOS is single-tenant and self-hosted: it holds one household's financial
data on infrastructure the owner controls. The security posture is aimed at that
threat model — protecting data at rest, resisting credential attacks, and
preventing the common web vulnerabilities — rather than multi-tenant isolation.

---

## Authentication

- **First-run setup** (`POST /api/v1/auth/setup`) creates the single owner
  account and seeds default categories/institutions. Once any user exists, setup
  is refused with **409 Conflict** — there is no open registration.
- **Login** issues a **server-side session** (`user_sessions` row): sessions are
  revocable and listable, and expire after `SESSION_MAX_AGE` (default 14 days).
- **Session cookie** — the session id is stored in an **HttpOnly**, `SameSite=Lax`
  cookie, cryptographically **signed and timestamped** with `itsdangerous`
  (`core/security.py`). Set `SESSION_COOKIE_SECURE=true` in production so the
  cookie is only sent over HTTPS.
- **Rate limiting** — login attempts are throttled per client IP
  (`LOGIN_MAX_ATTEMPTS` within `LOGIN_WINDOW_SECONDS`) to slow brute force. This
  is an in-process throttle suited to a single instance.

## Password hashing — Argon2id

Passwords are hashed with **Argon2id** via `argon2-cffi` (`PasswordHasher`
defaults, which are current and strong). Hashes are stored in
`users.password_hash`; verification is constant-time within the library, and
`needs_rehash` allows transparent upgrades as parameters harden. Setup and
change-password enforce a minimum length (10 chars) at the schema layer.

## Session cookies & CSRF (double-submit)

Because auth is cookie-based, state-changing requests are protected with a
**double-submit CSRF token** (`core/csrf.py`):

- On login/setup the server also sets a **non-HttpOnly** `capitalos_csrf` cookie.
- The SPA reads that cookie and echoes it in the `X-CSRF-Token` header on unsafe
  methods (POST/PUT/PATCH/DELETE).
- The `CSRFMiddleware` enforces a match **only when a session cookie is present**
  (where CSRF actually matters) and uses a constant-time comparison. Mismatched
  or missing tokens are rejected with **403**.

Additional response hardening (set in `main.py`): `X-Content-Type-Options:
nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
`Permissions-Policy` locking down device APIs, HSTS in production, and a
per-request `X-Request-ID` for correlation. Production also enforces
`TrustedHostMiddleware`.

## Field-level encryption (Fernet)

Sensitive fields are encrypted at the application layer with **Fernet**
(AES-128-CBC + HMAC, from `cryptography`) before they hit the database
(`core/security.py::encrypt_str` / `decrypt_str`):

- **Account IBANs** — accepted as plaintext, stored as `accounts.encrypted_iban`.
- **TOTP secrets** — `users.encrypted_totp_secret` (the TOTP flow itself is
  deferred; the storage is encryption-ready).

The key is `ENCRYPTION_KEY` (a valid Fernet key, validated at config load). In
production it is **required**; if absent in development a deterministic key is
derived from `SECRET_KEY` so dev values stay decryptable across restarts.

> **Losing `ENCRYPTION_KEY` means encrypted fields become unrecoverable.** See
> `BACKUP_AND_RECOVERY.md` — the key must be backed up separately from the
> database dump.

## CSV-injection-safe exports

Financial data is exportable to CSV. To prevent **CSV/formula injection** (a
cell beginning with `=`, `+`, `-`, `@`, tab or CR being executed as a formula
when opened in a spreadsheet), exported cell values that start with one of those
characters are neutralised (prefixed so they are treated as text). Exports are
generated server-side for the authenticated owner only.

## Configuration fail-fast

`core/config.py` refuses to boot in production (`APP_ENV=production`) when any of
these are insecure: `SECRET_KEY` unset/placeholder, `ENCRYPTION_KEY` missing,
`POSTGRES_PASSWORD` unset/placeholder (without an explicit `DATABASE_URL`), or
`SESSION_COOKIE_SECURE` not enabled. This turns misconfiguration into a startup
error rather than a silent vulnerability.

## Auditing

Security-relevant and data-changing events (setup, login, logout, session
revocation, account/transaction mutations) are written to `audit_logs` with
actor, action, entity, source IP, user-agent and before/after snapshots.

## Network posture

- **Dev** (`docker-compose.dev.yml`): Postgres and the backend bind to
  `127.0.0.1` only.
- **Prod** (`docker-compose.yml`): only Caddy is published (80/443); Postgres is
  reachable only on the private Docker network. Caddy provides automatic HTTPS
  and re-applies security headers at the edge.

---

## Deferred hardening (not in this build)

- **TOTP 2FA** — storage exists; enrolment/verification flow not implemented.
- **Distributed / persistent rate limiting** — current throttle is in-process
  and single-instance (resets on restart; not shared across replicas).
- **Automated key rotation** for `SECRET_KEY` / `ENCRYPTION_KEY`.
- **Automated, off-site, scheduled encrypted backups** — scripts are provided;
  scheduling and off-site upload are left to the operator.
- **Content-Security-Policy** tuned to the SPA, WAF, and intrusion detection.
- **Open Banking credential handling** — feature is flagged off.
