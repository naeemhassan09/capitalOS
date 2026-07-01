"""Reserve policy schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ReserveBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    jurisdiction: str = "IE"
    currency: str = Field(min_length=3, max_length=3)
    target_amount: Decimal = Decimal("0")
    protected_amount: Decimal = Decimal("0")
    hard_floor: Decimal | None = None
    preferred_target: Decimal | None = None
    months_of_coverage: int | None = None
    monthly_expense_basis: Decimal | None = None
    linked_account_ids: list[uuid.UUID] | None = None
    active: bool = True


class ReserveCreate(ReserveBase):
    pass


class ReserveUpdate(BaseModel):
    name: str | None = None
    jurisdiction: str | None = None
    currency: str | None = None
    target_amount: Decimal | None = None
    protected_amount: Decimal | None = None
    hard_floor: Decimal | None = None
    preferred_target: Decimal | None = None
    months_of_coverage: int | None = None
    monthly_expense_basis: Decimal | None = None
    linked_account_ids: list[uuid.UUID] | None = None
    active: bool | None = None


class ReserveOut(ORMModel):
    id: uuid.UUID
    name: str
    jurisdiction: str
    currency: str
    target_amount: Decimal
    protected_amount: Decimal
    hard_floor: Decimal | None
    preferred_target: Decimal | None
    months_of_coverage: int | None
    monthly_expense_basis: Decimal | None
    linked_account_ids: list[uuid.UUID] | None
    active: bool
    created_at: datetime
    updated_at: datetime
