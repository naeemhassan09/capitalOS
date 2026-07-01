# CapitalOS

**Privacy-first, self-hosted personal & household finance.**

CapitalOS is a single-tenant finance backend + SPA for someone whose money spans
**two jurisdictions** (the reference scenario is Ireland/EUR and Pakistan/PKR).
Its headline metric is **True Deployable Capital** — what you can actually spend
or invest after protected reserves and near-term committed expenses are removed —
computed globally *and* per jurisdiction. All data lives on infrastructure you
control; there are no third-party data processors in the core build.

- **Backend:** FastAPI (Python 3.12) · SQLAlchemy 2.0 · Alembic · PostgreSQL 16
- **Frontend:** React + Vite (served separately)
- **Runtime:** Docker Compose (+ Caddy for production HTTPS)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and the
authoritative deployable-capital formula, and [`docs/SECURITY.md`](docs/SECURITY.md)
for the security model.

---

## Features

- **Multi-jurisdiction, multi-currency** — Ireland/EUR + Pakistan/PKR (plus USD/GBP/SAR), all converted to your base currency with historical FX preserved.
- **True Deployable Capital** — liquid assets − current liabilities − near-term committed expenses − protected reserves, computed globally *and* per jurisdiction, so positive liquidity in one country never hides a deficit in another.
- **Dashboard** — settled vs projected position, upcoming obligations (90-day), currency exposure, goal progress, and honest risk warnings (never shows green when below a reserve floor).
- **Net Worth register** — every account *and* holding in one place, grouped by country, with ring-fenced reserves tagged “not deployable.”
- **Daily transactions** — add expenses, income, and account-to-account transfers (double-entry) by hand; account balances update live. Plus bulk categorise, inline edit, and transfer-matching.
- **Accounts** — banks, cash, cards and loans grouped by country/type; manual balance adjustment with an audit trail.
- **CSV import** — AIB / Revolut / generic importers with versioned-fingerprint de-duplication, preview, and safe batch rollback.
- **Planning** — scheduled cash flows (recurring), reserve policies, savings goals, and 7/30/60/90-day cash-flow projections with base/conservative/optimistic scenarios.
- **Investments** — holdings with cost basis, gain/loss, asset & currency allocation, and liquidity classes.
- **Reports & exports** — monthly, category spending, net-worth history, liabilities, goal funding; CSV/JSON export (spreadsheet-formula-injection safe).
- **Security & privacy** — Argon2id auth, server-side sessions, CSRF, field encryption for sensitive values, audit logging; fully self-hosted with no third-party data processors.

---

## Prerequisites

- **Docker** and the **Docker Compose** plugin. That's it — Python, Node and
  Postgres all run in containers. (Local Python is only needed if you want to
  run tools outside Docker.)
- `make` (optional, but every workflow below is wrapped in a Make target).

---

## Quickstart

```bash
# 1. Create your local .env from the template (fills in dev-safe defaults).
make setup
#    Then edit .env — at minimum set SECRET_KEY and ENCRYPTION_KEY for anything
#    beyond throwaway local use. Generation commands are in .env.example.

# 2. Start the full dev stack (Postgres + backend + frontend, hot-reload).
make dev
```

Then open **http://localhost:5173** and complete the **first-run setup** to
create the owner account (email, password, base currency, timezone). The backend
API and OpenAPI docs are at **http://localhost:8000/api/docs**.

### Loading data

```bash
make seed        # anonymised demo data (safe to commit / share)
make seed-real   # YOUR real figures — local only, gitignored
```

- `make seed` creates a demo owner `demo@capitalos.local` and prints its
  password and a computed True-Deployable-Capital summary. The demo scenario is
  deliberately built so gross assets look healthy while deployable capital sits
  near/below zero, and IE vs PK liquidity stay separate.
- `make seed-real` reads your password from `SEED_REAL_PASSWORD` (or generates
  and prints one), loads the real dataset from `backend/scripts/seed_real.py`,
  and prints the computed deployable capital so you can eyeball it. **That file
  contains personal data and is gitignored — never commit it.**

Both seed scripts are idempotent: they reset the owner's financial rows (keeping
the user, categories and institutions) before reloading.

### Testing

```bash
make test        # runs the backend test suite in a one-off container
```

The suite has two tiers (see [Testing](#testing-1)):

- **Pure calculation tests** — no database; always run.
- **Integration tests** — need Postgres; auto-skipped if unavailable.

---

## Make commands

| Command            | What it does                                                       |
|--------------------|-------------------------------------------------------------------|
| `make help`        | List all targets.                                                 |
| `make setup`       | Create `.env` from `.env.example` if missing.                     |
| `make dev`         | Start the full dev stack (foreground, hot-reload).                |
| `make up`          | Start the stack in the background.                                |
| `make stop`        | Stop containers, keep data.                                       |
| `make down`        | Stop and remove containers, keep volumes.                         |
| `make logs`        | Tail logs.                                                        |
| `make ps`          | Show container status.                                            |
| `make migration m="msg"` | Autogenerate an Alembic migration.                          |
| `make migrate`     | Apply migrations (`alembic upgrade head`).                        |
| `make seed`        | Load anonymised demo data.                                        |
| `make seed-real`   | Load your real figures (local only).                             |
| `make test`        | Run the backend test suite.                                       |
| `make lint`        | `ruff check` + `mypy`.                                            |
| `make format`      | `ruff format` + `ruff --fix`.                                     |
| `make shell`       | Open a backend shell.                                             |
| `make db-shell`    | Open a `psql` shell.                                              |
| `make backup`      | Run a database backup (see `BACKUP_AND_RECOVERY.md`).            |
| `make restore f=…` | Restore from a backup file.                                       |
| `make prod-build`  | Build production images (`docker-compose.yml`).                   |
| `make security-scan` | Pointer to the CI security scans.                              |

---

## Project layout

```
CapitalOS/
├── backend/
│   ├── app/
│   │   ├── api/v1/          HTTP routers
│   │   ├── calculations/    PURE financial logic (unit-tested, no DB)
│   │   ├── core/            config, db, security, csrf, deps
│   │   ├── importers/       CSV bank-statement parsers
│   │   ├── models/          SQLAlchemy ORM (money = Numeric, never float)
│   │   ├── providers/       FX rate resolution
│   │   ├── repositories/    user-scoped query helpers
│   │   ├── schemas/         Pydantic models
│   │   ├── services/        DB-aware business logic + ORM→view adapters
│   │   └── tests/           pure calc tests + integration tests
│   ├── scripts/             seed_common / seed_demo / seed_real
│   └── alembic/             migrations
├── frontend/                React + Vite SPA
├── deploy/
│   ├── caddy/               Caddyfile (prod reverse proxy)
│   └── scripts/             backup.sh / restore.sh / verify-backup.sh
├── docs/                    ARCHITECTURE.md, SECURITY.md
├── docker-compose.dev.yml   local dev stack
├── docker-compose.yml       production stack (Caddy + Postgres private)
└── Makefile
```

---

## Testing

Run everything with `make test`. Details:

- **Pure calculation tests** (`app/tests/test_calc_*.py`, `test_fingerprint.py`)
  exercise `app/calculations/*` with hand-built view fixtures and a stub
  converter. They cover: deployable capital excluding reserves **and** committed
  expenses (a big-gross-assets scenario yielding negative deployable), settled
  vs projected positions, reserve exclusion, credit-card-payment and
  internal-transfer exclusion from spending, injected-FX behaviour (different
  rate tables ⇒ different results, i.e. nothing is hard-coded), goal funding
  math, recurring-cashflow expansion counts, and duplicate-fingerprint
  determinism.
- **Integration tests** (`test_auth.py`, `test_accounts.py`, marked
  `integration`) run the FastAPI app against a throwaway `<db>_test` database:
  setup → login → me → logout, second-setup rejection (409), account
  CRUD/archive, and transaction create + duplicate (409). They are **skipped
  automatically** if Postgres is unreachable, so the pure calc tests still run
  anywhere.

`conftest.py` provisions the test DB (connecting to the maintenance `postgres`
database with AUTOCOMMIT to `CREATE DATABASE`), wraps each test in a rolled-back
SAVEPOINT, and provides `db`, `client`, and `auth_client` fixtures.

---

## Production deployment (multi-site VPS)

CapitalOS ships with a **multi-site** deployment layout under `deploy/`: a shared
**Caddy** reverse proxy (automatic **Let's Encrypt** TLS for every domain) and a
shared **Postgres** where each site gets its own database + role, so one VPS can
host several isolated apps efficiently. Each app is its own Compose stack joining
two shared networks (`edge`, `dbnet`).

```
deploy/
├── edge/                     shared Caddy + Postgres (the only public entrypoint)
│   ├── docker-compose.yml
│   ├── Caddyfile             one block per domain
│   └── .env.example
├── stacks/capitalos/         the CapitalOS app stack (no own DB/proxy)
│   ├── docker-compose.yml
│   └── .env.example
└── scripts/
    ├── bootstrap.sh          idempotent VPS provisioning (Docker/UFW/fail2ban/swap)
    ├── provision-db.sh       create an isolated DB + role for a site
    ├── deploy-capitalos.sh   build + migrate + start + verify
    ├── harden-ssh.sh         key-only SSH (run after key login confirmed)
    └── backup.sh / restore.sh / verify-backup.sh
```

Full step-by-step (SSH-key setup, bootstrap, TLS, first-run) is in
[`DEPLOYMENT.md`](DEPLOYMENT.md). Adding another website later is a new stack
folder + one Caddy block + `provision-db.sh <site>`.

## Deferred (not in this build)

The following are intentionally **out of scope** for this build. Some are
modelled or stubbed (columns/config/scripts exist) but not fully wired:

- **TOTP two-factor auth** — `users.encrypted_totp_secret` and `totp_enabled`
  columns and the `TOTP_ISSUER` setting exist, but the enrolment/verify flow is
  not implemented.
- **CI/CD** — `.github/workflows/ci.yml` runs lint/type/test/security on push,
  but there is no continuous-delivery / auto-deploy stage.
- **Encrypted nightly backup automation** — `deploy/scripts/*.sh` are provided
  and documented (`BACKUP_AND_RECOVERY.md`), but scheduling (cron/systemd/off-site
  upload) is left to the operator.
- **Open Banking** — `OPEN_BANKING_ENABLED` and GoCardless settings exist but the
  feature is flagged off and unimplemented; import is via CSV only.
- **Redis / Celery background workers** — `REDIS_URL` is reserved; there are no
  async workers or scheduled jobs in the core build.
- **Playwright end-to-end tests** — not included; testing is backend unit +
  integration only.
