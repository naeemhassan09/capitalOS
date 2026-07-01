# CapitalOS — Architecture

CapitalOS is a privacy-first, self-hosted personal- and household-finance
backend. It is a single-tenant application: one household, one owner account (a
spouse can be modelled as a household member). Everything runs on infrastructure
you control — no third-party data processors in the core build.

- **Backend:** FastAPI (Python 3.12), SQLAlchemy 2.0 ORM, Alembic migrations.
- **Database:** PostgreSQL 16.
- **Frontend:** React + Vite SPA (served separately; not covered here).
- **Deployment:** Docker Compose; Caddy reverse proxy for production HTTPS.

---

## 1. System overview

```
                    ┌────────────┐      HTTPS      ┌──────────────┐
   browser  ──────► │   Caddy    │ ──────────────► │  React SPA   │
                    │  (prod TLS)│                 │  (static)    │
                    └─────┬──────┘                 └──────────────┘
                          │ /api/*
                          ▼
                    ┌────────────┐   SQLAlchemy    ┌──────────────┐
                    │  FastAPI   │ ──────────────► │  PostgreSQL  │
                    │  backend   │                 │              │
                    └────────────┘                 └──────────────┘
```

Backend package layout (`backend/app/`):

| Package         | Responsibility                                                        |
|-----------------|-----------------------------------------------------------------------|
| `models/`       | SQLAlchemy ORM tables. Money columns are `Numeric(20,4)` — never float.|
| `schemas/`      | Pydantic request/response models.                                     |
| `api/v1/`       | HTTP routers (auth, accounts, transactions, goals, reserves, …).      |
| `services/`     | DB-aware business logic (auth, defaults, transactions, views, dashboard).|
| `calculations/` | **Pure** financial functions — no DB, no FastAPI. Unit-tested.        |
| `providers/`    | Adapters to the outside world (FX rate resolution).                   |
| `importers/`    | CSV bank-statement parsers (AIB, Revolut, generic).                   |
| `repositories/` | Small user-scoped query helpers.                                      |
| `core/`         | Config, DB engine, security, CSRF, dependencies.                      |

The **key architectural boundary** is between `services/` (impure, touches the
database) and `calculations/` (pure, deterministic). Services load ORM rows,
convert them to plain *view* dataclasses (`services/views.py`), and hand those —
plus an injected currency converter — to the calculation functions. This keeps
the financial logic fully unit-testable with hand-built fixtures and no
database (see `app/tests/test_calc_*.py`).

---

## 2. The two-jurisdiction financial model

CapitalOS is built for someone whose financial life spans **two jurisdictions**
— in the reference scenario, Ireland (EUR) and Pakistan (PKR) — with additional
incidental holdings in USD, GBP and SAR.

Money in one jurisdiction is not freely usable in the other (transfer friction,
FX cost, regulatory limits, family obligations). So the system tracks liquidity
**per jurisdiction** as well as in aggregate:

- Every `Account`, `ReservePolicy` and (derived) `Holding` carries a country /
  jurisdiction (`IE`, `PK`, `OTHER`).
- `deployable_capital(...)` returns a global figure **and** a per-jurisdiction
  breakdown (`by_jurisdiction`), so "I have money, but it's the wrong money in
  the wrong country" is visible rather than hidden by a single net number.

All values are converted to the user's **base currency** (EUR by default) for
comparison, using rates the user maintains (see §5).

---

## 3. The calculation layer & the deployable-capital formula

The headline metric is **True Deployable Capital**: money genuinely free to
spend or invest, after everything that is already spoken for is removed.

### Authoritative formula (spec §6.5)

```
deployable = liquid_assets
           − current_liabilities
           − committed_future_expenses(horizon)
           − protected_reserves
           − minimum_operating_cash
```

Implemented in `app/calculations/positions.py::deployable_capital`. Each term:

- **`liquid_assets`** — positive balances of non-liability accounts that are
  flagged `include_in_liquid_assets`, plus holdings whose `liquidity_class` is
  "immediate" (configurable). Restricted/illiquid assets (pension, property) are
  excluded.
- **`current_liabilities`** — the absolute value of every negative account
  balance (credit cards, loans). Balances are **signed**: a card owing €117 is
  stored as `-117`.
- **`committed_future_expenses(horizon)`** — scheduled *outflows* whose due date
  falls within the horizon (default 30 days), expanded from recurrence rules by
  `calculations/recurrence.py`. Inflows do **not** reduce deployable capital.
- **`protected_reserves`** — the sum of `ReservePolicy.protected_amount` (see
  §4). This is the reserve-as-classification principle in action.
- **`minimum_operating_cash`** — an optional floor of day-to-day working cash.

Because every currency term passes through the injected `convert` callable, the
formula is currency-agnostic and the same code produces both the global total
and each jurisdiction's sub-total.

### Related pure calculations

| Module          | Provides                                                              |
|-----------------|----------------------------------------------------------------------|
| `positions.py`  | settled position, liquid assets, liabilities, reserves, net worth, currency exposure, deployable capital |
| `projections.py`| projected position and daily balance series over a horizon, with base/conservative/optimistic scenarios |
| `spending.py`   | net spending, income, by category/account/country/member, essential vs discretionary, savings rate |
| `goals.py`      | goal funding progress, required monthly contribution, on-track status |
| `transfers.py`  | internal-transfer matching (incl. cross-currency, FX-implied)         |
| `recurrence.py` | expansion of scheduled cashflows into dated occurrences (RFC 5545 RRULE) |
| `money.py`      | `Decimal` helpers (`D`, `money`, `dsum`) — the money-is-never-float rule |

---

## 4. "A reserve is a classification, not an extra asset"

This is a load-bearing principle. A reserve (emergency fund, family ring-fence,
operating floor) is money you **already hold**, tagged as untouchable — it is
**not** a separate asset to be added on top.

Concretely:

- A `ReservePolicy` records a `protected_amount` that is **subtracted** from
  deployable capital. It does not create value.
- The money backing a reserve lives in a normal `Account`. That account can stay
  in liquid assets / net worth; the reserve line simply removes the same amount
  from what is *deployable*. Counting it in both liquid assets and as a separate
  holding would double-count it.
- Seed data enforces this. In `scripts/seed_real.py`, the spouse's ring-fenced
  PKR 300,000 is modelled **once**: as the `Ayesha MCB` account plus a matching
  `ReservePolicy`. The spreadsheet's duplicate "cash — Pakistan 300,000" holding
  is intentionally omitted (see the reconciliation note in that file and spec
  §6.6).

`SavingsGoal` rows may mirror reserves for UI/progress purposes (a "met",
`protected` emergency-reserve goal), but the authoritative subtraction from
deployable capital comes from `ReservePolicy`, not from goals.

---

## 5. FX handling and historical preservation

Rates are user-maintained rows in `exchange_rates`. Each row means:

> `1 base_currency = rate quote_currency` on `rate_date`.

`providers/fx.py::ManualFxProvider` resolves a conversion between any two
currencies by:

1. Selecting the **latest** rate per `(base, quote)` pair on or before a given
   date.
2. Building a directed `RateGraph` (each rate also yields its reciprocal edge).
3. BFS for the fewest-hop multiplicative path, enabling triangulation
   (e.g. `USD → PKR → EUR`) when a direct pair is missing.

`converter(base_currency, on_date)` returns a `convert(amount, currency)`
closure that the pure calculation layer consumes. The converter is always
**injected** — nothing in `calculations/` hard-codes a rate. The test
`test_calc_deployable.py::test_fx_converter_is_injected_not_hardcoded` asserts
this by feeding two different rate tables and requiring different results.

**Historical preservation:** because rate resolution accepts an `on_date` and
selects rows with `rate_date <= on_date`, a valuation "as of" a past date uses
the rates that were current then, not today's. Transactions can also persist
their own `exchange_rate` / `base_currency_amount` at the time they were booked,
so re-running a report never silently rewrites history with newer rates.

---

## 6. Data model summary

All rows are scoped by `user_id` (single-tenant, but the column keeps queries
explicit and cascade deletes clean). UUID primary keys; timestamps on most
tables.

| Table                | Purpose / notable fields                                             |
|----------------------|---------------------------------------------------------------------|
| `users`              | owner + auth (`password_hash` Argon2id, `encrypted_totp_secret`), `base_currency`, `timezone` |
| `user_sessions`      | server-side sessions (revocable, listable), expiry                  |
| `household_members`  | self / spouse / child; optional login link                          |
| `institutions`       | banks, brokers, credit unions, cash                                 |
| `accounts`           | signed `current_balance`, `country`, `currency`, `include_in_*`, `is_protected_reserve`, encrypted IBAN |
| `transactions`       | signed ledger; `fingerprint` (unique per account) for dedup; `kind`, `status`, `is_transfer` |
| `categories`         | hierarchical; `is_essential`, `is_income`, `is_system`              |
| `categorisation_rules`| deterministic auto-categorisation, `priority`-ordered              |
| `scheduled_cashflows`| planned in/out-flows; RRULE recurrence; drives committed expenses   |
| `savings_goals`      | target, contributions, `protected`, `goal_type`                     |
| `reserve_policies`   | `protected_amount`, `hard_floor`, `jurisdiction` — the subtraction  |
| `holdings` + `valuation_history` | investments; `native_currency`, `latest_valuation`, `liquidity_class` |
| `exchange_rates`     | user FX rows; unique per `(user, base, quote, rate_date)`           |
| `import_batches`     | CSV ingestion tracking + rollback                                   |
| `audit_logs`         | security-relevant and data-changing events                          |

Money columns use `Numeric(20,4)` (`MONEY`); rates/quantities use
`Numeric(20,8)` (`RATE`). The Python layer coerces everything through
`calculations.money.D` to `Decimal`.

---

## 7. Request lifecycle & security touchpoints

1. Caddy terminates TLS and proxies `/api/*` to FastAPI (production).
2. Middleware: CORS → TrustedHost (prod) → CSRF (double-submit) → correlation-id
   and security headers.
3. Auth dependency resolves a signed session cookie to a `User`.
4. Router validates input via Pydantic, calls a service, which commits.
5. Reads that need financial metrics go router → `services/views.py`
   (ORM → view dataclasses) → `calculations/*` (pure) → response.

See `docs/SECURITY.md` for the security model in detail.
