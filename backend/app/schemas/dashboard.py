"""Dashboard and cashflow-forecast response schemas.

These mirror the dict produced by ``app.services.dashboard.build_dashboard`` and
``app.api.v1.dashboard`` cashflow endpoint. Money is Decimal end-to-end.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class WarningOut(BaseModel):
    level: str  # "danger" | "warning" | "info"
    code: str
    message: str


class SettledOut(BaseModel):
    assets_base: Decimal
    liabilities_base: Decimal
    net_base: Decimal


class JurisdictionDeployableOut(BaseModel):
    country: str
    liquid_base: Decimal
    liabilities_base: Decimal
    committed_expenses_base: Decimal
    protected_reserves_base: Decimal
    min_operating_cash_base: Decimal
    deployable_base: Decimal


class DeployableOut(BaseModel):
    as_of: date
    horizon_days: int
    liquid_assets_base: Decimal
    current_liabilities_base: Decimal
    committed_expenses_base: Decimal
    protected_reserves_base: Decimal
    min_operating_cash_base: Decimal
    total_base: Decimal
    by_jurisdiction: list[JurisdictionDeployableOut]


class ProjectedPositionOut(BaseModel):
    horizon_days: int
    as_of: date
    target_date: date
    starting_net_base: Decimal
    projected_inflows_base: Decimal
    projected_outflows_base: Decimal
    projected_net_base: Decimal
    delta_base: Decimal


class JurisdictionCashOut(BaseModel):
    country: str
    deployable_base: Decimal
    projected_30d_net_base: Decimal
    hard_floor_base: Decimal


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


class NetWorthOut(BaseModel):
    liquid_net_worth_base: Decimal
    financial_ex_property_base: Decimal
    total_net_worth_base: Decimal
    retirement_assets_base: Decimal
    protected_reserves_base: Decimal
    investable_assets_base: Decimal
    liabilities_base: Decimal


class ObligationOut(BaseModel):
    name: str
    due_date: date
    amount: Decimal
    currency: str
    base_amount: Decimal
    country: str


class DashboardOut(BaseModel):
    as_of: date
    base_currency: str
    fx_available: bool
    settled: SettledOut
    settled_by_currency: dict[str, Decimal]
    liquid_assets_base: Decimal
    protected_reserves_base: Decimal
    current_liabilities_base: Decimal
    deployable: DeployableOut
    projected_30d: ProjectedPositionOut
    jurisdiction_cash: list[JurisdictionCashOut]
    monthly_income_base: Decimal
    monthly_expenses_base: Decimal
    savings_rate: Decimal
    rolling_3m_avg_spend_base: Decimal
    rolling_6m_avg_spend_base: Decimal
    goals: list[GoalProgressOut]
    net_worth: NetWorthOut
    currency_exposure: dict[str, Decimal]
    upcoming_obligations: list[ObligationOut]
    warnings: list[WarningOut]


# ---------------------------------------------------------- cashflow forecast
class DailyBalancePointOut(BaseModel):
    day: date
    balance_base: Decimal
    inflow_base: Decimal
    outflow_base: Decimal


class CashflowForecastOut(BaseModel):
    scenario: str
    horizon_days: int
    as_of: date
    base_currency: str
    starting_net_base: Decimal
    minimum_balance_base: Decimal
    minimum_balance_day: date | None
    points: list[DailyBalancePointOut]
    obligations: list[ObligationOut]
    warnings: list[WarningOut]
