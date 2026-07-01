"""Reporting endpoints: monthly, category spending, net-worth history,
liabilities, goal funding and annual summary."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.calculations.goals import compute_goal_progress
from app.calculations.money import ZERO, D
from app.calculations.positions import net_worth
from app.calculations.spending import (
    net_spending,
    savings_rate,
    spending_by_category,
    total_income,
)
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.providers.fx import FxError, ManualFxProvider
from app.schemas.reports import (
    AnnualSummaryOut,
    CategoryAmountOut,
    CategorySpendingOut,
    GoalFundingReportOut,
    LiabilitiesReportOut,
    MonthlyReportOut,
    NetWorthHistoryOut,
)
from app.services.views import (
    load_account_views,
    load_goal_views,
    load_holding_views,
    load_reserve_views,
    load_transaction_views,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _make_convert(db: Session, user: User, warnings: list[str]):
    """Build a converter that records missing-rate issues into ``warnings``."""
    missing: set[tuple[str, str]] = set()
    base = user.base_currency
    try:
        convert = ManualFxProvider(db, user.id).converter(base)
    except FxError:
        warnings.append("No exchange rates configured; values shown at par.")

        def convert(amount, currency):  # type: ignore[misc]
            return D(amount)

    def safe_convert(amount, currency):
        try:
            return convert(D(amount), currency)
        except FxError:
            key = (currency.upper(), base.upper())
            if key not in missing:
                missing.add(key)
                warnings.append(
                    f"Missing exchange rate {key[0]}->{key[1]}; value shown at par."
                )
            return D(amount)

    return safe_convert


def _by_category_list(mapping: dict[str, Decimal]) -> list[CategoryAmountOut]:
    return [
        CategoryAmountOut(category=k, amount_base=v)
        for k, v in sorted(mapping.items(), key=lambda kv: kv[1], reverse=True)
    ]


@router.get("/monthly", response_model=MonthlyReportOut)
def monthly_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MonthlyReportOut:
    warnings: list[str] = []
    convert = _make_convert(db, user, warnings)

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    txns = load_transaction_views(db, user.id, start, end)

    income = total_income(txns, convert)
    expenses = net_spending(txns, convert)
    by_cat = spending_by_category(txns, convert)

    return MonthlyReportOut(
        year=year,
        month=month,
        period_start=start,
        period_end=end,
        base_currency=user.base_currency,
        income_base=income,
        expenses_base=expenses,
        net_base=income - expenses,
        savings_rate=savings_rate(income, expenses),
        by_category=_by_category_list(by_cat),
        warnings=warnings,
    )


@router.get("/category-spending", response_model=CategorySpendingOut)
def category_spending_report(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CategorySpendingOut:
    # Default to the trailing 30 days so the dashboard can call this dateless.
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=30))
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to must be >= date_from")

    warnings: list[str] = []
    convert = _make_convert(db, user, warnings)

    txns = load_transaction_views(db, user.id, date_from, date_to)
    by_cat = spending_by_category(txns, convert)
    total = sum(by_cat.values(), ZERO)

    return CategorySpendingOut(
        date_from=date_from,
        date_to=date_to,
        base_currency=user.base_currency,
        total_base=total,
        by_category=_by_category_list(by_cat),
        warnings=warnings,
    )


@router.get("/net-worth-history", response_model=NetWorthHistoryOut)
def net_worth_history_report(
    months: int = Query(12, ge=1, le=120),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NetWorthHistoryOut:
    warnings: list[str] = []
    convert = _make_convert(db, user, warnings)

    accounts = load_account_views(db, user.id)
    holdings = load_holding_views(db, user.id)
    reserves = load_reserve_views(db, user.id)

    today = date.today()
    points = []
    for i in range(months):
        total = (today.year * 12 + (today.month - 1)) - i
        y, m0 = divmod(total, 12)
        m = m0 + 1
        month_end = date(y, m, monthrange(y, m)[1])
        # Historical valuations are not stored per snapshot, so we recompute
        # against *current* balances. This is an approximation, flagged below.
        nw = net_worth(accounts, holdings, reserves, convert)
        points.append(
            {
                "month_end": month_end,
                "total_net_worth_base": nw.total_net_worth_base,
                "liquid_net_worth_base": nw.liquid_net_worth_base,
                "liabilities_base": nw.liabilities_base,
                "approximated": True,
            }
        )
    points.sort(key=lambda p: p["month_end"])

    return NetWorthHistoryOut(
        base_currency=user.base_currency,
        months=months,
        note=(
            "Historical net worth is approximated using current balances; no "
            "per-month valuation history exists yet, so every point reflects "
            "today's positions."
        ),
        points=points,
        warnings=warnings,
    )


@router.get("/liabilities", response_model=LiabilitiesReportOut)
def liabilities_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LiabilitiesReportOut:
    warnings: list[str] = []
    convert = _make_convert(db, user, warnings)

    accounts = load_account_views(db, user.id)
    lines = []
    total = ZERO
    for a in accounts:
        bal = D(a.balance)
        # A liability by type, or any account currently in the red.
        if not (a.is_liability or bal < 0):
            continue
        bal_base = convert(bal, a.currency)
        total += -bal_base if bal < 0 else ZERO
        utilisation = None
        if a.credit_limit is not None and D(a.credit_limit) > 0:
            utilisation = abs(bal) / D(a.credit_limit)
        lines.append(
            {
                "account_id": a.id,
                "name": a.name,
                "account_type": a.account_type,
                "currency": a.currency,
                "country": a.country,
                "balance": bal,
                "balance_base": bal_base,
                "credit_limit": D(a.credit_limit) if a.credit_limit is not None else None,
                "utilisation": utilisation,
            }
        )
    lines.sort(key=lambda x: x["balance_base"])

    return LiabilitiesReportOut(
        base_currency=user.base_currency,
        total_liabilities_base=total,
        liabilities=lines,
        warnings=warnings,
    )


@router.get("/goal-funding", response_model=GoalFundingReportOut)
def goal_funding_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalFundingReportOut:
    today = date.today()
    goals = load_goal_views(db, user.id)
    out = []
    for gv in goals:
        gp = compute_goal_progress(gv, today)
        out.append(
            {
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
        )
    return GoalFundingReportOut(goals=out)


@router.get("/annual-summary", response_model=AnnualSummaryOut)
def annual_summary_report(
    year: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnnualSummaryOut:
    warnings: list[str] = []
    convert = _make_convert(db, user, warnings)

    start = date(year, 1, 1)
    end = date(year, 12, 31)
    txns = load_transaction_views(db, user.id, start, end)

    income = total_income(txns, convert)
    expenses = net_spending(txns, convert)
    by_cat = spending_by_category(txns, convert)

    return AnnualSummaryOut(
        year=year,
        period_start=start,
        period_end=end,
        base_currency=user.base_currency,
        income_base=income,
        expenses_base=expenses,
        net_base=income - expenses,
        savings_rate=savings_rate(income, expenses),
        by_category=_by_category_list(by_cat),
        warnings=warnings,
    )
