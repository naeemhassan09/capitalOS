"""Projected positions and daily balance forecasts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.calculations.money import ZERO, D
from app.calculations.types import CashflowOccurrence, Converter

# Scenario multipliers applied to *discretionary* projected outflows/inflows.
SCENARIOS: dict[str, tuple[Decimal, Decimal]] = {
    # name: (inflow_multiplier, outflow_multiplier)
    "base": (Decimal("1.0"), Decimal("1.0")),
    "conservative": (Decimal("0.9"), Decimal("1.1")),
    "optimistic": (Decimal("1.05"), Decimal("0.95")),
}


@dataclass
class ProjectedPosition:
    horizon_days: int
    as_of: date
    target_date: date
    starting_net_base: Decimal
    projected_inflows_base: Decimal
    projected_outflows_base: Decimal
    projected_net_base: Decimal
    delta_base: Decimal


@dataclass
class DailyBalancePoint:
    day: date
    balance_base: Decimal
    inflow_base: Decimal
    outflow_base: Decimal


@dataclass
class DailyBalanceSeries:
    scenario: str
    starting_net_base: Decimal
    points: list[DailyBalancePoint] = field(default_factory=list)
    minimum_balance_base: Decimal = ZERO
    minimum_balance_day: date | None = None


def projected_position(
    starting_net_base: Decimal,
    occurrences: Sequence[CashflowOccurrence],
    convert: Converter,
    as_of: date,
    horizon_days: int,
    scenario: str = "base",
) -> ProjectedPosition:
    in_mult, out_mult = SCENARIOS.get(scenario, SCENARIOS["base"])
    target = as_of + timedelta(days=horizon_days)
    inflows = ZERO
    outflows = ZERO
    for o in occurrences:
        if not (as_of <= o.due_date <= target):
            continue
        base = convert(D(o.amount), o.currency)
        if o.direction == "inflow":
            inflows += base * in_mult
        else:
            outflows += base * out_mult
    net = starting_net_base + inflows - outflows
    return ProjectedPosition(
        horizon_days=horizon_days,
        as_of=as_of,
        target_date=target,
        starting_net_base=starting_net_base,
        projected_inflows_base=inflows,
        projected_outflows_base=outflows,
        projected_net_base=net,
        delta_base=net - starting_net_base,
    )


def daily_balance_series(
    starting_net_base: Decimal,
    occurrences: Sequence[CashflowOccurrence],
    convert: Converter,
    as_of: date,
    horizon_days: int,
    scenario: str = "base",
) -> DailyBalanceSeries:
    in_mult, out_mult = SCENARIOS.get(scenario, SCENARIOS["base"])
    by_day_in: dict[date, Decimal] = {}
    by_day_out: dict[date, Decimal] = {}
    target = as_of + timedelta(days=horizon_days)
    for o in occurrences:
        if not (as_of <= o.due_date <= target):
            continue
        base = convert(D(o.amount), o.currency)
        if o.direction == "inflow":
            by_day_in[o.due_date] = by_day_in.get(o.due_date, ZERO) + base * in_mult
        else:
            by_day_out[o.due_date] = by_day_out.get(o.due_date, ZERO) + base * out_mult

    series = DailyBalanceSeries(scenario=scenario, starting_net_base=starting_net_base)
    balance = starting_net_base
    min_balance = starting_net_base
    min_day = as_of
    for i in range(horizon_days + 1):
        day = as_of + timedelta(days=i)
        inflow = by_day_in.get(day, ZERO)
        outflow = by_day_out.get(day, ZERO)
        balance = balance + inflow - outflow
        if balance < min_balance:
            min_balance = balance
            min_day = day
        series.points.append(DailyBalancePoint(day, balance, inflow, outflow))
    series.minimum_balance_base = min_balance
    series.minimum_balance_day = min_day
    return series
