"""Report endpoint response schemas. Money is Decimal end-to-end."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CategoryAmountOut(BaseModel):
    category: str
    amount_base: Decimal


class MonthlyReportOut(BaseModel):
    year: int
    month: int
    period_start: date
    period_end: date
    base_currency: str
    income_base: Decimal
    expenses_base: Decimal
    net_base: Decimal
    savings_rate: Decimal
    by_category: list[CategoryAmountOut]
    warnings: list[str] = []


class CategorySpendingOut(BaseModel):
    date_from: date
    date_to: date
    base_currency: str
    total_base: Decimal
    by_category: list[CategoryAmountOut]
    warnings: list[str] = []


class NetWorthPointOut(BaseModel):
    month_end: date
    total_net_worth_base: Decimal
    liquid_net_worth_base: Decimal
    liabilities_base: Decimal
    approximated: bool


class NetWorthHistoryOut(BaseModel):
    base_currency: str
    months: int
    note: str
    points: list[NetWorthPointOut]
    warnings: list[str] = []


class LiabilityLineOut(BaseModel):
    account_id: str
    name: str
    account_type: str
    currency: str
    country: str
    balance: Decimal
    balance_base: Decimal
    credit_limit: Decimal | None
    utilisation: Decimal | None


class LiabilitiesReportOut(BaseModel):
    base_currency: str
    total_liabilities_base: Decimal
    liabilities: list[LiabilityLineOut]
    warnings: list[str] = []


class GoalFundingOut(BaseModel):
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


class GoalFundingReportOut(BaseModel):
    goals: list[GoalFundingOut]


class AnnualSummaryOut(BaseModel):
    year: int
    period_start: date
    period_end: date
    base_currency: str
    income_base: Decimal
    expenses_base: Decimal
    net_base: Decimal
    savings_rate: Decimal
    by_category: list[CategoryAmountOut]
    warnings: list[str] = []
