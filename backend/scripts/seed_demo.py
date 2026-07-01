"""Seed anonymised demo data — safe to commit and safe to share.

Run inside the backend container::

    python -m scripts.seed_demo          # (== make seed)

Scenario (fictional): a two-jurisdiction household split between Ireland (EUR)
and Pakistan (PKR). It is deliberately constructed so that although *gross*
assets look healthy, the *true deployable capital* — what is genuinely free to
spend/invest after subtracting protected reserves and committed near-term
expenses — is at or below zero. It also keeps Irish and Pakistani liquidity
separate so the per-jurisdiction breakdown is meaningful.

Nothing here maps to a real person; the figures are illustrative only.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.calculations.positions import deployable_capital, net_worth
from app.calculations.recurrence import expand_occurrences
from app.core.db import SessionLocal
from app.providers.fx import ManualFxProvider
from app.services.views import (
    load_account_views,
    load_holding_views,
    load_reserve_views,
    load_scheduled_views,
)

from scripts.seed_common import (
    category_by_slug,
    get_or_create_owner,
    make_account,
    make_goal,
    make_holding,
    make_rate,
    make_reserve,
    make_scheduled,
    make_transaction,
    reset_user_data,
)

# NOTE: this password is intentionally printed and committed — the demo dataset
# is disposable and never contains real personal data.
DEMO_EMAIL = "demo@capitalos.local"
DEMO_PASSWORD = "Demo-Capital-OS-2026!"  # noqa: S105 - documented demo credential
DEMO_NAME = "Demo User"

TODAY = date.today()


def _cat(db, user_id, slug):
    c = category_by_slug(db, user_id, slug)
    return c.id if c else None


def seed(db) -> None:
    owner = get_or_create_owner(
        db,
        email=DEMO_EMAIL,
        password=DEMO_PASSWORD,
        display_name=DEMO_NAME,
        base_currency="EUR",
        timezone="Europe/Dublin",
    )
    reset_user_data(db, owner.id)
    uid = owner.id

    # ------------------------------------------------------------- FX rates
    # 1 base = rate quote. Base currency is EUR.
    make_rate(db, user_id=uid, base_currency="EUR", quote_currency="PKR",
              rate=Decimal("325"), rate_date=TODAY)
    make_rate(db, user_id=uid, base_currency="USD", quote_currency="PKR",
              rate=Decimal("282"), rate_date=TODAY)
    make_rate(db, user_id=uid, base_currency="SAR", quote_currency="PKR",
              rate=Decimal("75"), rate_date=TODAY)
    make_rate(db, user_id=uid, base_currency="GBP", quote_currency="PKR",
              rate=Decimal("360"), rate_date=TODAY)

    # ======================================================= IRELAND (EUR)
    aib = make_account(db, user_id=uid, name="AIB Current", account_type="current",
                       currency="EUR", country="IE", balance=Decimal("2100"),
                       institution="AIB")
    revolut = make_account(db, user_id=uid, name="Revolut", account_type="current",
                           currency="EUR", country="IE", balance=Decimal("240"),
                           institution="Revolut")
    eur_cash = make_account(db, user_id=uid, name="EUR Cash", account_type="cash",
                            currency="EUR", country="IE", balance=Decimal("160"),
                            institution="Cash")
    # Irish credit card — a liability, stored as a negative balance.
    make_account(db, user_id=uid, name="AIB Credit Card", account_type="credit_card",
                 currency="EUR", country="IE", balance=Decimal("-540"),
                 credit_limit=Decimal("4000"), institution="AIB")

    # Monthly rent (outflow) and salary (inflow), both recurring monthly.
    make_scheduled(db, user_id=uid, name="Rent", direction="outflow",
                   amount=Decimal("1450"), currency="EUR", first_due_date=TODAY.replace(day=1),
                   account_id=aib.id, category_id=_cat(db, uid, "housing-rent"),
                   recurrence_rule="FREQ=MONTHLY;BYMONTHDAY=1", priority=10)
    make_scheduled(db, user_id=uid, name="Salary", direction="inflow",
                   amount=Decimal("3200"), currency="EUR", first_due_date=TODAY.replace(day=25),
                   account_id=aib.id, category_id=_cat(db, uid, "income-salary"),
                   recurrence_rule="FREQ=MONTHLY;BYMONTHDAY=25", priority=10)

    # Goals (Ireland).
    make_goal(db, user_id=uid, name="Travel — Summer Trip", currency="EUR",
              target_amount=Decimal("1500"), goal_type="travel",
              manual_contributed_amount=Decimal("300"),
              target_date=TODAY + timedelta(days=150), priority=60)
    make_goal(db, user_id=uid, name="Car Fund", currency="EUR",
              target_amount=Decimal("6000"), goal_type="car_purchase",
              manual_contributed_amount=Decimal("500"),
              target_date=TODAY + timedelta(days=365), priority=50)

    # Ireland operating-floor reserve: EUR 2,000 protected.
    make_reserve(db, user_id=uid, name="Ireland operating floor", currency="EUR",
                 jurisdiction="IE", protected_amount=Decimal("2000"),
                 hard_floor=Decimal("2000"))

    # ====================================================== PAKISTAN (PKR)
    meezan = make_account(db, user_id=uid, name="Meezan Bank", account_type="savings",
                          currency="PKR", country="PK", balance=Decimal("420000"),
                          institution="Meezan Bank")
    # MCB account that holds a ring-fenced family reserve.
    mcb = make_account(db, user_id=uid, name="MCB Reserve Account", account_type="savings",
                       currency="PKR", country="PK", balance=Decimal("300000"),
                       institution="MCB", is_protected_reserve=True)
    # Pakistani credit card — liability.
    make_account(db, user_id=uid, name="Pakistan Credit Card", account_type="credit_card",
                 currency="PKR", country="PK", balance=Decimal("-85000"),
                 credit_limit=Decimal("500000"), institution="Standard Chartered Pakistan")

    # Recurring household expense (outflow).
    make_scheduled(db, user_id=uid, name="Pakistan household", direction="outflow",
                   amount=Decimal("120000"), currency="PKR",
                   first_due_date=TODAY.replace(day=5),
                   account_id=meezan.id, category_id=_cat(db, uid, "family-pakistan-household"),
                   recurrence_rule="FREQ=MONTHLY;BYMONTHDAY=5", priority=10)

    # Family reserve: PKR 300,000 ring-fenced (backed by the MCB account).
    make_reserve(db, user_id=uid, name="Family reserve (Pakistan)", currency="PKR",
                 jurisdiction="PK", protected_amount=Decimal("300000"),
                 months_of_coverage=6, linked_account_ids=[mcb.id])

    # Holdings: mutual fund, spouse stock, pension.
    make_holding(db, user_id=uid, asset_name="Al Meezan Mutual Fund", asset_class="mutual_fund",
                 native_currency="PKR", valuation=Decimal("150000"),
                 liquidity_class="short_term")
    make_holding(db, user_id=uid, asset_name="Spouse stock portfolio", asset_class="stock",
                 native_currency="PKR", valuation=Decimal("200000"),
                 liquidity_class="short_term")
    make_holding(db, user_id=uid, asset_name="Pension", asset_class="pension",
                 native_currency="PKR", valuation=Decimal("400000"),
                 liquidity_class="restricted")

    # ---------------------------------------- a handful of past transactions
    _seed_history(db, uid, aib, revolut, eur_cash, meezan)

    db.flush()


def _seed_history(db, uid, aib, revolut, eur_cash, meezan) -> None:
    """Assorted booked transactions across a few categories (illustrative)."""
    d = TODAY

    def cat(slug):
        return _cat(db, uid, slug)

    make_transaction(db, user_id=uid, account=aib, booking_date=d - timedelta(days=2),
                     amount=Decimal("62.40"), direction="debit", description="Tesco groceries",
                     kind="expense", category_id=cat("food-groceries"))
    make_transaction(db, user_id=uid, account=aib, booking_date=d - timedelta(days=5),
                     amount=Decimal("48.00"), direction="debit", description="Electric Ireland",
                     kind="expense", category_id=cat("housing-utilities"))
    make_transaction(db, user_id=uid, account=revolut, booking_date=d - timedelta(days=7),
                     amount=Decimal("12.99"), direction="debit", description="Spotify",
                     kind="expense", category_id=cat("lifestyle-subscriptions"))
    make_transaction(db, user_id=uid, account=revolut, booking_date=d - timedelta(days=9),
                     amount=Decimal("34.50"), direction="debit", description="Dinner out",
                     kind="expense", category_id=cat("food-eating-out"))
    make_transaction(db, user_id=uid, account=eur_cash, booking_date=d - timedelta(days=11),
                     amount=Decimal("20.00"), direction="debit", description="Bus top-up",
                     kind="expense", category_id=cat("transport-public-transport"))
    make_transaction(db, user_id=uid, account=aib, booking_date=d - timedelta(days=1),
                     amount=Decimal("3200.00"), direction="credit", description="Monthly salary",
                     kind="income", category_id=cat("income-salary"))
    make_transaction(db, user_id=uid, account=meezan, booking_date=d - timedelta(days=4),
                     amount=Decimal("18000.00"), direction="debit",
                     description="Family groceries", kind="expense",
                     category_id=cat("family-pakistan-household"))


def _print_summary(db, owner) -> None:
    """Compute true deployable capital via the calculation layer and print it."""
    uid = owner.id
    convert = ManualFxProvider(db, uid).converter(owner.base_currency)

    accounts = load_account_views(db, uid)
    holdings = load_holding_views(db, uid)
    reserves = load_reserve_views(db, uid)
    scheduled = load_scheduled_views(db, uid)
    horizon = 30
    occurrences = expand_occurrences(scheduled, TODAY, TODAY + timedelta(days=horizon))

    nw = net_worth(accounts, holdings, reserves, convert)
    dep = deployable_capital(
        accounts, holdings, reserves, occurrences, convert,
        as_of=TODAY, horizon_days=horizon,
    )

    line = "=" * 62
    print("\n" + line)
    print(f"  CapitalOS demo data seeded for {owner.email}")
    print(f"  Login password: {DEMO_PASSWORD}")
    print(line)
    print(f"  Base currency:                {owner.base_currency}")
    print(f"  Total net worth:              {nw.total_net_worth_base:>14,.2f}")
    print(f"  Financial (ex-property):      {nw.financial_ex_property_base:>14,.2f}")
    print(f"  Liquid assets:                {dep.liquid_assets_base:>14,.2f}")
    print(f"  - current liabilities:        {dep.current_liabilities_base:>14,.2f}")
    print(f"  - committed expenses ({horizon}d):  {dep.committed_expenses_base:>14,.2f}")
    print(f"  - protected reserves:         {dep.protected_reserves_base:>14,.2f}")
    print(line)
    print(f"  TRUE DEPLOYABLE CAPITAL:      {dep.total_base:>14,.2f}")
    print(line)
    print("  By jurisdiction (deployable):")
    for j in dep.by_jurisdiction:
        print(f"    {j.country:<6} liquid={j.liquid_base:>12,.2f}  "
              f"reserves={j.protected_reserves_base:>12,.2f}  "
              f"deployable={j.deployable_base:>12,.2f}")
    print(line)
    if dep.total_base <= 0:
        print("  Note: gross assets are healthy but TRUE deployable capital is")
        print("  at/below zero once reserves + committed expenses are removed.")
    print(line + "\n")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
        owner = get_or_create_owner(
            db, email=DEMO_EMAIL, password=DEMO_PASSWORD, display_name=DEMO_NAME
        )
        _print_summary(db, owner)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
