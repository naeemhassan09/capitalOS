"""Scheduled cashflow schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ScheduledCashflowBase(BaseModel):
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    direction: str  # inflow | outflow
    amount: Decimal  # positive magnitude
    currency: str = Field(min_length=3, max_length=3)
    first_due_date: date
    next_due_date: date | None = None
    recurrence_rule: str | None = None
    end_date: date | None = None
    occurrence_count: int | None = None
    priority: int = 100
    status: str = "planned"
    auto_match: bool = True


class ScheduledCashflowCreate(ScheduledCashflowBase):
    pass


class ScheduledCashflowUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    direction: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    first_due_date: date | None = None
    next_due_date: date | None = None
    recurrence_rule: str | None = None
    end_date: date | None = None
    occurrence_count: int | None = None
    priority: int | None = None
    status: str | None = None
    auto_match: bool | None = None


class ScheduledCashflowOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    name: str
    description: str | None
    direction: str
    amount: Decimal
    currency: str
    first_due_date: date
    next_due_date: date
    recurrence_rule: str | None
    end_date: date | None
    occurrence_count: int | None
    priority: int
    status: str
    auto_match: bool
    created_at: datetime
    updated_at: datetime
