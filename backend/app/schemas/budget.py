"""Budget schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class BudgetCreate(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(ge=0)


class BudgetUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None


class BudgetOut(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    active: bool


class BudgetReportRow(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    amount: Decimal          # monthly limit (base currency)
    actual_base: Decimal     # spent this period
    remaining_base: Decimal  # amount - actual (may be negative = over budget)
    percent_used: Decimal    # 0..(>100)
    prev_month_base: Decimal
    avg_3m_base: Decimal


class BudgetReport(BaseModel):
    year: int
    month: int
    base_currency: str
    total_budget_base: Decimal
    total_actual_base: Decimal
    rows: list[BudgetReportRow]
