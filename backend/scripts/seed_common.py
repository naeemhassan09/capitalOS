"""Shared helpers for the seed scripts.

These run inside the backend container as, for example::

    python -m scripts.seed_demo

with the working directory ``/app`` (== ``backend/``), so ``import app...``
resolves. All money is handled as :class:`decimal.Decimal` — never float.

The public surface is intentionally small:

* :func:`get_or_create_owner` — idempotent owner bootstrap (seeds the default
  categories / institutions / self-member via ``services.auth.create_owner``).
* :func:`reset_user_data` — wipe a user's *financial* rows (accounts, txns,
  goals, reserves, holdings, scheduled cashflows, exchange rates) while keeping
  the user record itself plus its categories and institutions, so re-seeding is
  repeatable without duplicating the taxonomy.
* Lookup helpers for categories (by slug) and institutions (by name).
* Small typed constructors for accounts, holdings, reserves, goals, scheduled
  cashflows, transactions and exchange rates that fill in the required
  fingerprints / defaults so the scenario files stay declarative.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.models.account import Account
from app.models.category import Category
from app.models.exchange_rate import ExchangeRate
from app.models.goal import SavingsGoal
from app.models.holding import Holding
from app.models.institution import Institution
from app.models.reserve import ReservePolicy
from app.models.scheduled_cashflow import ScheduledCashflow
from app.models.transaction import Transaction
from app.models.user import User
from app.services.auth import create_owner, is_initialized
from app.services.transactions import build_fingerprint


# --------------------------------------------------------------------- owner
def get_or_create_owner(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    base_currency: str = "EUR",
    timezone: str = "Europe/Dublin",
) -> User:
    """Return the existing owner, or create it (seeding defaults) if the app is
    uninitialised.

    ``create_owner`` refuses to run once *any* user exists, so we only call it
    when :func:`is_initialized` is False. If an owner already exists we look it
    up by email (falling back to the first owner) so re-runs are idempotent.
    """
    if not is_initialized(db):
        owner = create_owner(
            db,
            email=email,
            password=password,
            display_name=display_name,
            base_currency=base_currency,
            timezone=timezone,
        )
        db.flush()
        return owner

    owner = db.scalar(select(User).where(User.email == email.lower().strip()))
    if owner is None:
        owner = db.scalar(select(User).where(User.is_owner.is_(True)).limit(1))
    if owner is None:  # pragma: no cover - only if a non-owner user somehow exists
        owner = db.scalar(select(User).limit(1))
    if owner is None:  # pragma: no cover - defensive
        raise RuntimeError("Application is initialised but no user could be found.")
    return owner


# ------------------------------------------------------------- data reset
# Order matters: children before parents to satisfy FKs even without cascades.
def reset_user_data(db: Session, user_id: uuid.UUID) -> None:
    """Delete a user's financial data but keep the user, categories and
    institutions (so the default taxonomy is preserved across re-seeds)."""
    # Transactions reference accounts (and cascade from accounts anyway).
    db.execute(delete(Transaction).where(Transaction.user_id == user_id))
    db.execute(delete(ScheduledCashflow).where(ScheduledCashflow.user_id == user_id))
    db.execute(delete(SavingsGoal).where(SavingsGoal.user_id == user_id))
    db.execute(delete(ReservePolicy).where(ReservePolicy.user_id == user_id))
    # Holdings may reference accounts via SET NULL; delete holdings first.
    db.execute(delete(Holding).where(Holding.user_id == user_id))
    db.execute(delete(Account).where(Account.user_id == user_id))
    db.execute(delete(ExchangeRate).where(ExchangeRate.user_id == user_id))
    db.flush()


# ---------------------------------------------------------------- lookups
def category_by_slug(db: Session, user_id: uuid.UUID, slug: str) -> Category | None:
    return db.scalar(
        select(Category).where(Category.user_id == user_id, Category.slug == slug)
    )


def institution_by_name(db: Session, user_id: uuid.UUID, name: str) -> Institution | None:
    return db.scalar(
        select(Institution).where(Institution.user_id == user_id, Institution.name == name)
    )


# ---------------------------------------------------------- constructors
def make_account(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    account_type: str,
    currency: str,
    country: str,
    balance: Decimal,
    institution: str | None = None,
    credit_limit: Decimal | None = None,
    include_in_net_worth: bool = True,
    include_in_liquid_assets: bool = True,
    is_protected_reserve: bool = False,
    balance_date: date | None = None,
) -> Account:
    """Create an account. ``balance`` is signed (liabilities negative)."""
    inst = institution_by_name(db, user_id, institution) if institution else None
    account = Account(
        user_id=user_id,
        institution_id=inst.id if inst else None,
        name=name,
        account_type=account_type,
        currency=currency.upper(),
        country=country,
        opening_balance=D(balance),
        current_balance=D(balance),
        balance_date=balance_date or date.today(),
        credit_limit=D(credit_limit) if credit_limit is not None else None,
        include_in_net_worth=include_in_net_worth,
        include_in_liquid_assets=include_in_liquid_assets,
        is_protected_reserve=is_protected_reserve,
    )
    db.add(account)
    db.flush()
    return account


def make_holding(
    db: Session,
    *,
    user_id: uuid.UUID,
    asset_name: str,
    asset_class: str,
    native_currency: str,
    valuation: Decimal,
    quantity: Decimal = Decimal("0"),
    liquidity_class: str = "immediate",
    account_id: uuid.UUID | None = None,
    include_in_net_worth: bool = True,
    notes: str | None = None,
    valuation_date: date | None = None,
) -> Holding:
    holding = Holding(
        user_id=user_id,
        account_id=account_id,
        asset_name=asset_name,
        asset_class=asset_class,
        native_currency=native_currency.upper(),
        quantity=D(quantity),
        latest_valuation=D(valuation),
        liquidity_class=liquidity_class,
        include_in_net_worth=include_in_net_worth,
        valuation_is_manual=True,
        valuation_date=valuation_date or date.today(),
        notes=notes,
    )
    db.add(holding)
    db.flush()
    return holding


def make_reserve(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    currency: str,
    jurisdiction: str,
    protected_amount: Decimal,
    hard_floor: Decimal | None = None,
    months_of_coverage: int | None = None,
    monthly_expense_basis: Decimal | None = None,
    linked_account_ids: list[uuid.UUID] | None = None,
) -> ReservePolicy:
    reserve = ReservePolicy(
        user_id=user_id,
        name=name,
        currency=currency.upper(),
        jurisdiction=jurisdiction,
        target_amount=D(protected_amount),
        protected_amount=D(protected_amount),
        hard_floor=D(hard_floor) if hard_floor is not None else None,
        months_of_coverage=months_of_coverage,
        monthly_expense_basis=(
            D(monthly_expense_basis) if monthly_expense_basis is not None else None
        ),
        linked_account_ids=[str(a) for a in linked_account_ids] if linked_account_ids else None,
        active=True,
    )
    db.add(reserve)
    db.flush()
    return reserve


def make_goal(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    currency: str,
    target_amount: Decimal,
    goal_type: str = "custom",
    manual_contributed_amount: Decimal = Decimal("0"),
    target_date: date | None = None,
    protected: bool = False,
    status: str = "active",
    priority: int = 100,
    linked_account_ids: list[uuid.UUID] | None = None,
) -> SavingsGoal:
    goal = SavingsGoal(
        user_id=user_id,
        name=name,
        currency=currency.upper(),
        target_amount=D(target_amount),
        goal_type=goal_type,
        manual_contributed_amount=D(manual_contributed_amount),
        target_date=target_date,
        protected=protected,
        status=status,
        priority=priority,
        linked_account_ids=[str(a) for a in linked_account_ids] if linked_account_ids else None,
    )
    db.add(goal)
    db.flush()
    return goal


def make_scheduled(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    direction: str,
    amount: Decimal,
    currency: str,
    first_due_date: date,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    recurrence_rule: str | None = None,
    end_date: date | None = None,
    occurrence_count: int | None = None,
    priority: int = 100,
    status: str = "planned",
) -> ScheduledCashflow:
    """Create a scheduled cashflow. ``amount`` is a positive magnitude."""
    cf = ScheduledCashflow(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        name=name,
        direction=direction,
        amount=D(amount),
        currency=currency.upper(),
        first_due_date=first_due_date,
        next_due_date=first_due_date,
        recurrence_rule=recurrence_rule,
        end_date=end_date,
        occurrence_count=occurrence_count,
        priority=priority,
        status=status,
    )
    db.add(cf)
    db.flush()
    return cf


def make_transaction(
    db: Session,
    *,
    user_id: uuid.UUID,
    account: Account,
    booking_date: date,
    amount: Decimal,
    direction: str,
    description: str,
    kind: str = "expense",
    currency: str | None = None,
    category_id: uuid.UUID | None = None,
    status: str = "booked",
    is_transfer: bool = False,
) -> Transaction:
    """Create a booked transaction with a computed fingerprint.

    ``amount`` is a positive magnitude; ``direction`` is ``credit``/``debit``.
    """
    cur = (currency or account.currency).upper()
    fingerprint = build_fingerprint(
        account_id=str(account.id),
        booking_date=booking_date,
        amount=amount,
        currency=cur,
        description=description,
    )
    txn = Transaction(
        user_id=user_id,
        account_id=account.id,
        booking_date=booking_date,
        description=description,
        amount=D(amount),
        currency=cur,
        direction=direction,
        kind=kind,
        status=status,
        category_id=category_id,
        is_transfer=is_transfer,
        is_reviewed=True,
        source="seed",
        fingerprint=fingerprint,
    )
    db.add(txn)
    db.flush()
    return txn


def make_rate(
    db: Session,
    *,
    user_id: uuid.UUID,
    base_currency: str,
    quote_currency: str,
    rate: Decimal,
    rate_date: date,
) -> ExchangeRate:
    """Create an exchange rate row: ``1 base_currency = rate quote_currency``."""
    fx = ExchangeRate(
        user_id=user_id,
        base_currency=base_currency.upper(),
        quote_currency=quote_currency.upper(),
        rate=D(rate),
        rate_date=rate_date,
        source="seed",
        is_manual=True,
    )
    db.add(fx)
    db.flush()
    return fx
