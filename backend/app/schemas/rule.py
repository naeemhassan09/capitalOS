"""Categorisation rule schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RuleBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    priority: int = 100

    match_field: str
    operator: str
    match_value: str
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None

    institution_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None

    normalized_merchant: str | None = None
    mark_as_transfer: bool = False
    mark_as_recurring: bool = False
    set_kind: str | None = None
    enabled: bool = True


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: str | None = None
    priority: int | None = None
    match_field: str | None = None
    operator: str | None = None
    match_value: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    institution_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    normalized_merchant: str | None = None
    mark_as_transfer: bool | None = None
    mark_as_recurring: bool | None = None
    set_kind: str | None = None
    enabled: bool | None = None


class RuleOut(ORMModel):
    id: uuid.UUID
    name: str
    priority: int
    match_field: str
    operator: str
    match_value: str
    amount_min: Decimal | None
    amount_max: Decimal | None
    institution_id: uuid.UUID | None
    account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    normalized_merchant: str | None
    mark_as_transfer: bool
    mark_as_recurring: bool
    set_kind: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RuleTestResult(BaseModel):
    matched_count: int
