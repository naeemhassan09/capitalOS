"""Plain view objects consumed by the pure calculation functions.

These are intentionally decoupled from ORM models so calculations can be unit
tested with hand-built fixtures and no database.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Converts (amount, currency) -> amount in the user's base currency.
Converter = Callable[[Decimal, str], Decimal]

LIABILITY_TYPES = {"credit_card", "loan", "other_liability"}


@dataclass(frozen=True)
class AccountView:
    id: str
    name: str
    currency: str
    country: str
    account_type: str
    balance: Decimal  # signed: assets positive, liabilities negative
    include_in_net_worth: bool = True
    include_in_liquid_assets: bool = True
    is_protected_reserve: bool = False
    is_archived: bool = False
    credit_limit: Decimal | None = None

    @property
    def is_liability(self) -> bool:
        return self.account_type in LIABILITY_TYPES


@dataclass(frozen=True)
class HoldingView:
    id: str
    asset_name: str
    asset_class: str
    native_currency: str
    valuation: Decimal
    cost_basis: Decimal | None = None
    liquidity_class: str = "immediate"
    include_in_net_worth: bool = True
    country: str = "OTHER"


@dataclass(frozen=True)
class CashflowOccurrence:
    due_date: date
    direction: str  # "inflow" | "outflow"
    amount: Decimal  # positive magnitude
    currency: str
    country: str = "OTHER"
    name: str = ""
    priority: int = 100


@dataclass(frozen=True)
class ReserveView:
    id: str
    name: str
    currency: str
    jurisdiction: str
    protected_amount: Decimal
    hard_floor: Decimal | None = None


@dataclass(frozen=True)
class GoalView:
    id: str
    name: str
    currency: str
    target_amount: Decimal
    manual_contributed_amount: Decimal
    linked_account_balances: list[Decimal] = field(default_factory=list)
    target_date: date | None = None
    priority: int = 100
    protected: bool = False
