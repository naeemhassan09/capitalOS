"""Adapters converting ORM rows into pure-calculation view objects."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.calculations.recurrence import ScheduledCashflowView
from app.calculations.spending import TransactionView
from app.calculations.types import (
    AccountView,
    GoalView,
    HoldingView,
    ReserveView,
)
from app.models.account import Account
from app.models.category import Category
from app.models.goal import SavingsGoal
from app.models.holding import Holding
from app.models.reserve import ReservePolicy
from app.models.scheduled_cashflow import ScheduledCashflow
from app.models.transaction import Transaction

_CURRENCY_COUNTRY = {"EUR": "IE", "PKR": "PK", "GBP": "OTHER", "USD": "OTHER", "SAR": "OTHER"}


def _country_for_currency(currency: str) -> str:
    return _CURRENCY_COUNTRY.get(currency.upper(), "OTHER")


def account_view(a: Account) -> AccountView:
    return AccountView(
        id=str(a.id),
        name=a.name,
        currency=a.currency,
        country=a.country,
        account_type=a.account_type,
        balance=D(a.current_balance),
        include_in_net_worth=a.include_in_net_worth,
        include_in_liquid_assets=a.include_in_liquid_assets,
        is_protected_reserve=a.is_protected_reserve,
        is_archived=a.is_archived,
        credit_limit=D(a.credit_limit) if a.credit_limit is not None else None,
    )


def holding_view(h: Holding, account_country: dict[uuid.UUID, str]) -> HoldingView:
    country = "OTHER"
    if h.account_id and h.account_id in account_country:
        country = account_country[h.account_id]
    else:
        country = _country_for_currency(h.native_currency)
    return HoldingView(
        id=str(h.id),
        asset_name=h.asset_name,
        asset_class=h.asset_class,
        native_currency=h.native_currency,
        valuation=D(h.latest_valuation),
        cost_basis=D(h.cost_basis) if h.cost_basis is not None else None,
        liquidity_class=h.liquidity_class,
        include_in_net_worth=h.include_in_net_worth,
        country=country,
    )


def reserve_view(r: ReservePolicy) -> ReserveView:
    return ReserveView(
        id=str(r.id),
        name=r.name,
        currency=r.currency,
        jurisdiction=r.jurisdiction,
        protected_amount=D(r.protected_amount),
        hard_floor=D(r.hard_floor) if r.hard_floor is not None else None,
    )


def scheduled_view(s: ScheduledCashflow) -> ScheduledCashflowView:
    return ScheduledCashflowView(
        id=str(s.id),
        name=s.name,
        direction=s.direction,
        amount=D(s.amount),
        currency=s.currency,
        country=_country_for_currency(s.currency),
        first_due_date=s.first_due_date,
        recurrence_rule=s.recurrence_rule,
        end_date=s.end_date,
        priority=s.priority,
        status=s.status,
    )


def goal_view(g: SavingsGoal, account_balances: dict[uuid.UUID, Account]) -> GoalView:
    linked: list = []
    for aid in g.linked_account_ids or []:
        try:
            acc = account_balances.get(uuid.UUID(str(aid)))
        except ValueError:
            acc = None
        if acc is not None:
            linked.append(D(acc.current_balance))
    return GoalView(
        id=str(g.id),
        name=g.name,
        currency=g.currency,
        target_amount=D(g.target_amount),
        manual_contributed_amount=D(g.manual_contributed_amount),
        linked_account_balances=linked,
        target_date=g.target_date,
        priority=g.priority,
        protected=g.protected,
    )


# --------------------------------------------------------------- loaders
def load_accounts(db: Session, user_id: uuid.UUID) -> list[Account]:
    return list(
        db.scalars(
            select(Account).where(Account.user_id == user_id, Account.is_archived.is_(False))
        ).all()
    )


def load_account_views(db: Session, user_id: uuid.UUID) -> list[AccountView]:
    return [account_view(a) for a in load_accounts(db, user_id)]


def load_holding_views(db: Session, user_id: uuid.UUID) -> list[HoldingView]:
    accounts = {a.id: a.country for a in load_accounts(db, user_id)}
    holdings = db.scalars(select(Holding).where(Holding.user_id == user_id)).all()
    return [holding_view(h, accounts) for h in holdings]


def load_reserve_views(db: Session, user_id: uuid.UUID) -> list[ReserveView]:
    rows = db.scalars(
        select(ReservePolicy).where(
            ReservePolicy.user_id == user_id, ReservePolicy.active.is_(True)
        )
    ).all()
    return [reserve_view(r) for r in rows]


def load_scheduled_views(db: Session, user_id: uuid.UUID) -> list[ScheduledCashflowView]:
    rows = db.scalars(
        select(ScheduledCashflow).where(ScheduledCashflow.user_id == user_id)
    ).all()
    return [scheduled_view(s) for s in rows]


def load_goal_views(db: Session, user_id: uuid.UUID) -> list[GoalView]:
    accounts = {a.id: a for a in load_accounts(db, user_id)}
    rows = db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user_id)).all()
    return [goal_view(g, accounts) for g in rows]


def load_transaction_views(
    db: Session,
    user_id: uuid.UUID,
    start: date | None = None,
    end: date | None = None,
) -> list[TransactionView]:
    cat_map = {
        c.id: c
        for c in db.scalars(select(Category).where(Category.user_id == user_id)).all()
    }
    acc_map = {a.id: a for a in db.scalars(select(Account).where(Account.user_id == user_id)).all()}
    stmt = select(Transaction).where(Transaction.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Transaction.booking_date >= start)
    if end is not None:
        stmt = stmt.where(Transaction.booking_date <= end)
    txns = db.scalars(stmt).all()
    out: list[TransactionView] = []
    for t in txns:
        cat = cat_map.get(t.category_id) if t.category_id else None
        acc = acc_map.get(t.account_id)
        out.append(
            TransactionView(
                amount=D(t.amount),
                currency=t.currency,
                kind=t.kind,
                status=t.status,
                booking_date=t.booking_date,
                is_transfer=t.is_transfer,
                category_id=str(t.category_id) if t.category_id else None,
                category_name=cat.name if cat else "Uncategorised",
                account_id=str(t.account_id),
                account_name=acc.name if acc else "",
                country=acc.country if acc else "OTHER",
                is_essential=cat.is_essential if cat else False,
            )
        )
    return out


def account_country_map(accounts: Sequence[Account]) -> dict[uuid.UUID, str]:
    return {a.id: a.country for a in accounts}
