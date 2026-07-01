"""Dashboard aggregation service.

Pure orchestration: it loads ORM→view adapters, calls the *stable* calculation
functions, and returns plain ``dict`` structures (Decimals preserved). The
Pydantic response schemas are responsible for serialisation.

Nothing here recomputes money — it only wires existing building blocks together.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.calculations.goals import GoalProgress, compute_goal_progress
from app.calculations.money import ZERO, D
from app.calculations.positions import (
    currency_exposure,
    current_liabilities,
    deployable_capital,
    liquid_assets,
    net_worth,
    protected_reserves_total,
    settled_position,
)
from app.calculations.projections import projected_position
from app.calculations.recurrence import expand_occurrences
from app.calculations.spending import (
    net_spending,
    savings_rate,
    total_income,
)
from app.calculations.types import Converter, ReserveView
from app.models.transaction import Transaction
from app.models.user import User
from app.providers.fx import FxError, ManualFxProvider
from app.services.views import (
    load_account_views,
    load_goal_views,
    load_holding_views,
    load_reserve_views,
    load_scheduled_views,
    load_transaction_views,
)

# Jurisdictions surfaced with a dedicated cash breakdown on the dashboard.
JURISDICTIONS = ("IE", "PK")

DEPLOYABLE_HORIZON_DAYS = 30
PROJECTION_HORIZON_DAYS = 30
# How far ahead the "upcoming obligations" list looks (wider than the 30-day
# deployable horizon so near-future bills like next month's card statement show).
UPCOMING_WINDOW_DAYS = 90
# Window over which occurrences are expanded once and then reused.
OCCURRENCE_WINDOW_DAYS = 90

CREDIT_UTILISATION_WARN = Decimal("0.5")
REVIEW_LOOKBACK_DAYS = 60


def _fmt_amount(value, currency: str) -> str:
    """Human-friendly money for warning text, e.g. 'EUR -1,911.00'."""
    return f"{currency} {D(value):,.2f}"


def _month_bounds(as_of: date) -> tuple[date, date]:
    start = as_of.replace(day=1)
    last_day = monthrange(as_of.year, as_of.month)[1]
    end = as_of.replace(day=last_day)
    return start, end


def _months_back(as_of: date, months: int) -> date:
    """Return a date ``months`` calendar months before ``as_of`` (clamped day)."""
    total = (as_of.year * 12 + (as_of.month - 1)) - months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(as_of.day, monthrange(year, month)[1])
    return date(year, month, day)


def _jd_by_country(deployable) -> dict[str, object]:
    return {jd.country: jd for jd in deployable.by_jurisdiction}


def _reserve_hard_floor_base(
    reserves: list[ReserveView], country: str, convert: Converter
) -> Decimal:
    """Base-currency hard floor for a jurisdiction (0 if none defined)."""
    total = ZERO
    for r in reserves:
        if r.jurisdiction == country and r.hard_floor is not None:
            total += convert(D(r.hard_floor), r.currency)
    return total


def _goal_progress_to_dict(gp: GoalProgress) -> dict:
    return {
        "id": gp.id,
        "name": gp.name,
        "currency": gp.currency,
        "target_amount": gp.target_amount,
        "current_amount": gp.current_amount,
        "remaining_amount": gp.remaining_amount,
        "percent_funded": gp.percent_funded,
        "days_remaining": gp.days_remaining,
        "required_monthly_contribution": gp.required_monthly_contribution,
        "on_track": gp.on_track,
        "status": gp.status,
    }


def _serialize_deployable(deployable) -> dict:
    return {
        "as_of": deployable.as_of,
        "horizon_days": deployable.horizon_days,
        "liquid_assets_base": deployable.liquid_assets_base,
        "current_liabilities_base": deployable.current_liabilities_base,
        "committed_expenses_base": deployable.committed_expenses_base,
        "protected_reserves_base": deployable.protected_reserves_base,
        "min_operating_cash_base": deployable.min_operating_cash_base,
        "total_base": deployable.total_base,
        "by_jurisdiction": [
            {
                "country": jd.country,
                "liquid_base": jd.liquid_base,
                "liabilities_base": jd.liabilities_base,
                "committed_expenses_base": jd.committed_expenses_base,
                "protected_reserves_base": jd.protected_reserves_base,
                "min_operating_cash_base": jd.min_operating_cash_base,
                "deployable_base": jd.deployable_base,
            }
            for jd in deployable.by_jurisdiction
        ],
    }


def _serialize_net_worth(nw) -> dict:
    return {
        "liquid_net_worth_base": nw.liquid_net_worth_base,
        "financial_ex_property_base": nw.financial_ex_property_base,
        "total_net_worth_base": nw.total_net_worth_base,
        "retirement_assets_base": nw.retirement_assets_base,
        "protected_reserves_base": nw.protected_reserves_base,
        "investable_assets_base": nw.investable_assets_base,
        "liabilities_base": nw.liabilities_base,
    }


def build_dashboard(db: Session, user: User, as_of: date | None = None) -> dict:
    """Assemble the full dashboard payload as a Decimal-safe dict."""
    as_of = as_of or date.today()
    user_id: uuid.UUID = user.id
    base_currency = user.base_currency

    warnings: list[dict] = []

    # Build the converter once. If FX rows are missing entirely we still want a
    # usable (if degraded) dashboard, so we fall back to an identity-ish converter
    # and surface a warning rather than 500ing.
    fx_ok = True
    try:
        convert = ManualFxProvider(db, user_id).converter(base_currency)
    except FxError:
        fx_ok = False

        def convert(amount: Decimal, currency: str) -> Decimal:  # type: ignore[misc]
            # Only correct for same-currency values; other currencies are 1:1
            # placeholders. A warning is emitted below.
            return D(amount)

        warnings.append(
            {
                "level": "warning",
                "code": "fx_unavailable",
                "message": "No exchange rates configured; multi-currency values "
                "are shown at par and may be inaccurate.",
            }
        )

    # A converter that records missing-rate problems instead of raising.
    missing_pairs: set[tuple[str, str]] = set()

    def safe_convert(amount: Decimal, currency: str) -> Decimal:
        try:
            return convert(D(amount), currency)
        except FxError:
            missing_pairs.add((currency.upper(), base_currency.upper()))
            return D(amount)

    # ------------------------------------------------------------- load views
    accounts = load_account_views(db, user_id)
    holdings = load_holding_views(db, user_id)
    reserves = load_reserve_views(db, user_id)
    scheduled = load_scheduled_views(db, user_id)
    goals = load_goal_views(db, user_id)

    # Expand occurrences once over the whole window and reuse everywhere.
    window_end = as_of + timedelta(days=OCCURRENCE_WINDOW_DAYS)
    occurrences = expand_occurrences(scheduled, as_of, window_end)

    # ------------------------------------------------------------- positions
    settled = settled_position(accounts, safe_convert)
    settled_by_currency = currency_exposure(accounts, holdings, safe_convert)
    liquid_base = liquid_assets(accounts, holdings, safe_convert)
    protected_base = protected_reserves_total(reserves, safe_convert)
    liabilities_base = current_liabilities(accounts, safe_convert)

    deployable = deployable_capital(
        accounts,
        holdings,
        reserves,
        occurrences,
        safe_convert,
        as_of,
        horizon_days=DEPLOYABLE_HORIZON_DAYS,
    )

    projected_30d = projected_position(
        starting_net_base=settled.net_base,
        occurrences=occurrences,
        convert=safe_convert,
        as_of=as_of,
        horizon_days=PROJECTION_HORIZON_DAYS,
    )

    nw = net_worth(accounts, holdings, reserves, safe_convert)

    # -------------------------------------------------- jurisdiction cash
    jd_map = _jd_by_country(deployable)
    jurisdiction_cash: list[dict] = []
    for country in JURISDICTIONS:
        jd = jd_map.get(country)
        deployable_amt = jd.deployable_base if jd is not None else ZERO
        c_occurrences = [o for o in occurrences if o.country == country]
        c_proj = projected_position(
            starting_net_base=deployable_amt,
            occurrences=c_occurrences,
            convert=safe_convert,
            as_of=as_of,
            horizon_days=PROJECTION_HORIZON_DAYS,
        )
        hard_floor = _reserve_hard_floor_base(reserves, country, safe_convert)
        jurisdiction_cash.append(
            {
                "country": country,
                "deployable_base": deployable_amt,
                "projected_30d_net_base": c_proj.projected_net_base,
                "hard_floor_base": hard_floor,
            }
        )
        # Danger: projected jurisdiction cash below the jurisdiction hard floor.
        if hard_floor > 0 and c_proj.projected_net_base < hard_floor:
            warnings.append(
                {
                    "level": "danger",
                    "code": "jurisdiction_below_floor",
                    "message": (
                        f"Projected 30-day cash for {country} "
                        f"({_fmt_amount(c_proj.projected_net_base, base_currency)}) is "
                        f"below the reserve hard floor "
                        f"({_fmt_amount(hard_floor, base_currency)})."
                    ),
                }
            )

    # ---------------------------------------------- spending (current month)
    month_start, month_end = _month_bounds(as_of)
    month_txns = load_transaction_views(db, user_id, month_start, month_end)
    monthly_income = total_income(month_txns, safe_convert)
    monthly_expenses = net_spending(month_txns, safe_convert)
    monthly_savings_rate = savings_rate(monthly_income, monthly_expenses)

    # Rolling average spend (per month) over the trailing 3 / 6 months.
    def _rolling_avg_spend(months: int) -> Decimal:
        start = _months_back(as_of, months)
        txns = load_transaction_views(db, user_id, start, as_of)
        spent = net_spending(txns, safe_convert)
        return spent / Decimal(months) if months > 0 else ZERO

    rolling_3m = _rolling_avg_spend(3)
    rolling_6m = _rolling_avg_spend(6)

    # ------------------------------------------------------------- goals
    goal_dicts: list[dict] = []
    for gv in goals:
        gp = compute_goal_progress(gv, as_of)
        goal_dicts.append(_goal_progress_to_dict(gp))
        if not gp.on_track:
            warnings.append(
                {
                    "level": "warning",
                    "code": "goal_off_track",
                    "message": f"Goal '{gp.name}' is off track.",
                }
            )

    # ------------------------------ upcoming obligations (next 90 days)
    upcoming_end = as_of + timedelta(days=UPCOMING_WINDOW_DAYS)
    upcoming: list[dict] = []
    for o in occurrences:
        if o.direction != "outflow":
            continue
        if not (as_of <= o.due_date <= upcoming_end):
            continue
        upcoming.append(
            {
                "name": o.name,
                "due_date": o.due_date,
                "amount": D(o.amount),
                "currency": o.currency,
                "base_amount": safe_convert(D(o.amount), o.currency),
                "country": o.country,
            }
        )
    upcoming.sort(key=lambda x: (x["due_date"], x["name"]))

    # ----------------------------------------------------- warning: overdue
    for s in scheduled:
        overdue = s.status == "overdue" or (
            s.first_due_date < as_of and s.status not in {"paid", "cancelled"}
        )
        if overdue:
            warnings.append(
                {
                    "level": "warning",
                    "code": "scheduled_overdue",
                    "message": (
                        f"Scheduled cashflow '{s.name}' is overdue "
                        f"(due {s.first_due_date}, status {s.status})."
                    ),
                }
            )

    # --------------------------------------- warning: credit utilisation
    for a in accounts:
        if a.account_type != "credit_card" or a.credit_limit in (None, ZERO):
            continue
        limit = D(a.credit_limit)
        if limit <= 0:
            continue
        utilisation = abs(D(a.balance)) / limit
        if utilisation > CREDIT_UTILISATION_WARN:
            warnings.append(
                {
                    "level": "warning",
                    "code": "high_credit_utilisation",
                    "message": (
                        f"Credit card '{a.name}' utilisation is "
                        f"{(utilisation * Decimal(100)).quantize(Decimal('0.1'))}%."
                    ),
                }
            )

    # ----------------------------------- info: unreviewed transactions (60d)
    review_start = as_of - timedelta(days=REVIEW_LOOKBACK_DAYS)
    unreviewed_count = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.is_reviewed.is_(False),
            Transaction.booking_date >= review_start,
            Transaction.booking_date <= as_of,
        )
        .count()
    )
    if unreviewed_count > 0:
        warnings.append(
            {
                "level": "info",
                "code": "unreviewed_transactions",
                "message": (
                    f"{unreviewed_count} transaction(s) in the last "
                    f"{REVIEW_LOOKBACK_DAYS} days are not reviewed."
                ),
            }
        )

    # -------------------------------- danger: negative deployable capital
    if deployable.total_base < 0:
        warnings.append(
            {
                "level": "danger",
                "code": "negative_deployable",
                "message": (
                    "Deployable capital is negative "
                    f"({_fmt_amount(deployable.total_base, base_currency)}); "
                    "commitments exceed liquid, unprotected assets."
                ),
            }
        )

    # -------------------------------- missing-rate warnings (from converter)
    for frm, to in sorted(missing_pairs):
        warnings.append(
            {
                "level": "warning",
                "code": "fx_rate_missing",
                "message": f"Missing exchange rate {frm}->{to}; value shown at par.",
            }
        )

    return {
        "as_of": as_of,
        "base_currency": base_currency,
        "fx_available": fx_ok and not missing_pairs,
        "settled": {
            "assets_base": settled.assets_base,
            "liabilities_base": settled.liabilities_base,
            "net_base": settled.net_base,
        },
        "settled_by_currency": settled_by_currency,
        "liquid_assets_base": liquid_base,
        "protected_reserves_base": protected_base,
        "current_liabilities_base": liabilities_base,
        "deployable": _serialize_deployable(deployable),
        "projected_30d": {
            "horizon_days": projected_30d.horizon_days,
            "as_of": projected_30d.as_of,
            "target_date": projected_30d.target_date,
            "starting_net_base": projected_30d.starting_net_base,
            "projected_inflows_base": projected_30d.projected_inflows_base,
            "projected_outflows_base": projected_30d.projected_outflows_base,
            "projected_net_base": projected_30d.projected_net_base,
            "delta_base": projected_30d.delta_base,
        },
        "jurisdiction_cash": jurisdiction_cash,
        "monthly_income_base": monthly_income,
        "monthly_expenses_base": monthly_expenses,
        "savings_rate": monthly_savings_rate,
        "rolling_3m_avg_spend_base": rolling_3m,
        "rolling_6m_avg_spend_base": rolling_6m,
        "goals": goal_dicts,
        "net_worth": _serialize_net_worth(nw),
        "currency_exposure": settled_by_currency,
        "upcoming_obligations": upcoming,
        "warnings": warnings,
    }
