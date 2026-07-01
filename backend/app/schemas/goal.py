"""Savings goal schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class GoalBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    target_amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    target_date: date | None = None
    priority: int = 100
    goal_type: str = "custom"
    linked_account_ids: list[uuid.UUID] | None = None
    manual_contributed_amount: Decimal = Decimal("0")
    protected: bool = False
    status: str = "active"


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_amount: Decimal | None = None
    currency: str | None = None
    target_date: date | None = None
    priority: int | None = None
    goal_type: str | None = None
    linked_account_ids: list[uuid.UUID] | None = None
    manual_contributed_amount: Decimal | None = None
    protected: bool | None = None
    status: str | None = None


class GoalOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    target_amount: Decimal
    currency: str
    target_date: date | None
    priority: int
    goal_type: str
    linked_account_ids: list[uuid.UUID] | None
    manual_contributed_amount: Decimal
    protected: bool
    status: str
    created_at: datetime
    updated_at: datetime


class GoalProgressOut(BaseModel):
    id: str
    name: str
    currency: str
    target_amount: Decimal
    current_amount: Decimal
    remaining_amount: Decimal
    percent_funded: Decimal
    days_remaining: int | None
    required_monthly_contribution: Decimal | None
    on_track: bool
    status: str


class GoalWithProgress(BaseModel):
    goal: GoalOut
    progress: GoalProgressOut
