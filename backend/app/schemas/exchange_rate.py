"""Exchange rate schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ExchangeRateBase(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    rate: Decimal
    rate_date: date
    source: str = "manual"
    is_manual: bool = True


class ExchangeRateCreate(ExchangeRateBase):
    pass


class ExchangeRateUpdate(BaseModel):
    rate: Decimal | None = None
    source: str | None = None
    is_manual: bool | None = None


class ExchangeRateOut(ORMModel):
    id: uuid.UUID
    base_currency: str
    quote_currency: str
    rate: Decimal
    rate_date: date
    source: str
    is_manual: bool
    created_at: datetime


class ConversionResult(BaseModel):
    amount: Decimal
    from_currency: str
    to_currency: str
    on_date: date | None
    converted: Decimal
