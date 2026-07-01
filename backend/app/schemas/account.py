"""Account schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_type: str
    account_subtype: str | None = None
    currency: str = Field(min_length=3, max_length=3)
    country: str = "IE"
    institution_id: uuid.UUID | None = None
    owner_member_id: uuid.UUID | None = None
    masked_identifier: str | None = None
    iban: str | None = None  # plaintext in; stored encrypted
    opening_balance: Decimal = Decimal("0")
    current_balance: Decimal = Decimal("0")
    balance_date: date | None = None
    credit_limit: Decimal | None = None
    include_in_net_worth: bool = True
    include_in_liquid_assets: bool = True
    is_protected_reserve: bool = False
    account_metadata: dict | None = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: str | None = None
    account_subtype: str | None = None
    institution_id: uuid.UUID | None = None
    owner_member_id: uuid.UUID | None = None
    masked_identifier: str | None = None
    iban: str | None = None
    current_balance: Decimal | None = None
    balance_date: date | None = None
    credit_limit: Decimal | None = None
    include_in_net_worth: bool | None = None
    include_in_liquid_assets: bool | None = None
    is_protected_reserve: bool | None = None
    is_archived: bool | None = None
    account_metadata: dict | None = None


class BalanceAdjustment(BaseModel):
    new_balance: Decimal
    note: str | None = None
    as_of: date | None = None


class AccountOut(ORMModel):
    id: uuid.UUID
    name: str
    account_type: str
    account_subtype: str | None
    currency: str
    country: str
    institution_id: uuid.UUID | None
    owner_member_id: uuid.UUID | None
    masked_identifier: str | None
    opening_balance: Decimal
    current_balance: Decimal
    balance_date: date | None
    credit_limit: Decimal | None
    include_in_net_worth: bool
    include_in_liquid_assets: bool
    is_protected_reserve: bool
    is_archived: bool
    account_metadata: dict | None
    created_at: datetime
    updated_at: datetime
