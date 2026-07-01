"""Investment holding and valuation schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# Validated vocabularies — must match app.models.enums (AssetClass/LiquidityClass).
AssetClassStr = Literal[
    "cash", "stock", "etf", "mutual_fund", "pension", "crypto",
    "commodity", "property", "private_equity", "other",
]
LiquidityClassStr = Literal["immediate", "short_term", "restricted", "illiquid"]


class HoldingBase(BaseModel):
    account_id: uuid.UUID | None = None
    asset_name: str = Field(min_length=1, max_length=160)
    ticker: str | None = None
    asset_class: AssetClassStr = "other"
    quantity: Decimal = Decimal("0")
    native_currency: str = Field(min_length=3, max_length=3)
    cost_basis: Decimal | None = None
    latest_unit_price: Decimal | None = None
    latest_valuation: Decimal = Decimal("0")
    valuation_date: date | None = None
    liquidity_class: LiquidityClassStr = "immediate"
    include_in_net_worth: bool = True
    valuation_is_manual: bool = True
    notes: str | None = None


class HoldingCreate(HoldingBase):
    pass


class HoldingUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    asset_name: str | None = None
    ticker: str | None = None
    asset_class: AssetClassStr | None = None
    quantity: Decimal | None = None
    native_currency: str | None = None
    cost_basis: Decimal | None = None
    latest_unit_price: Decimal | None = None
    latest_valuation: Decimal | None = None
    valuation_date: date | None = None
    liquidity_class: LiquidityClassStr | None = None
    include_in_net_worth: bool | None = None
    valuation_is_manual: bool | None = None
    notes: str | None = None


class HoldingOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    asset_name: str
    ticker: str | None
    asset_class: str
    quantity: Decimal
    native_currency: str
    cost_basis: Decimal | None
    latest_unit_price: Decimal | None
    latest_valuation: Decimal
    valuation_date: date | None
    liquidity_class: str
    include_in_net_worth: bool
    valuation_is_manual: bool
    notes: str | None
    gain_loss: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class ValuationCreate(BaseModel):
    valuation_date: date
    valuation: Decimal
    unit_price: Decimal | None = None
    source: str = "manual"


class ValuationOut(ORMModel):
    id: uuid.UUID
    holding_id: uuid.UUID
    valuation_date: date
    unit_price: Decimal | None
    valuation: Decimal
    source: str
    created_at: datetime
    updated_at: datetime
