"""Budget report: planned limits vs actual spend, with comparisons."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import ZERO, D
from app.calculations.spending import EXCLUDED_STATUSES, REFUND_KINDS, SPENDING_KINDS
from app.models.budget import Budget
from app.models.category import Category
from app.models.user import User
from app.providers.fx import ManualFxProvider
from app.services.views import load_transaction_views


def _spend_by_category(db: Session, user: User, convert, start: date, end: date
                       ) -> dict[str, Decimal]:
    """Net spending per category_id (base currency) over [start, end]."""
    out: dict[str, Decimal] = {}
    for t in load_transaction_views(db, user.id, start, end):
        if t.is_transfer or t.status in EXCLUDED_STATUSES or not t.category_id:
            continue
        if t.kind in SPENDING_KINDS:
            out[t.category_id] = out.get(t.category_id, ZERO) + convert(D(t.amount), t.currency)
        elif t.kind in REFUND_KINDS:
            out[t.category_id] = out.get(t.category_id, ZERO) - convert(D(t.amount), t.currency)
    return out


def build_budget_report(db: Session, user: User, year: int, month: int) -> dict:
    convert = ManualFxProvider(db, user.id).converter(user.base_currency)

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    prev = start - relativedelta(months=1)
    prev_start = date(prev.year, prev.month, 1)
    prev_end = date(prev.year, prev.month, monthrange(prev.year, prev.month)[1])
    three_start = start - relativedelta(months=2)  # 3-month window ending this month

    this_spend = _spend_by_category(db, user, convert, start, end)
    prev_spend = _spend_by_category(db, user, convert, prev_start, prev_end)
    three_spend = _spend_by_category(db, user, convert, three_start, end)

    cat_names = {
        c.id: c.name
        for c in db.scalars(select(Category).where(Category.user_id == user.id)).all()
    }
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == user.id, Budget.active.is_(True))
    ).all()

    rows = []
    total_budget = ZERO
    total_actual = ZERO
    for b in budgets:
        cid = str(b.category_id)
        amount = D(b.amount)
        actual = this_spend.get(cid, ZERO)
        percent = (actual / amount * Decimal(100)) if amount > 0 else ZERO
        total_budget += amount
        total_actual += actual
        rows.append(
            {
                "id": b.id,
                "category_id": b.category_id,
                "category_name": cat_names.get(b.category_id, "Uncategorised"),
                "amount": amount,
                "actual_base": actual,
                "remaining_base": amount - actual,
                "percent_used": percent,
                "prev_month_base": prev_spend.get(cid, ZERO),
                "avg_3m_base": three_spend.get(cid, ZERO) / Decimal(3),
            }
        )
    rows.sort(key=lambda r: r["category_name"])
    return {
        "year": year,
        "month": month,
        "base_currency": user.base_currency,
        "total_budget_base": total_budget,
        "total_actual_base": total_actual,
        "rows": rows,
    }
