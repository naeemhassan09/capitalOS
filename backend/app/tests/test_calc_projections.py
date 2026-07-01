"""Pure tests for projected positions and daily balance forecasts."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.calculations.projections import (
    SCENARIOS,
    daily_balance_series,
    projected_position,
)
from app.calculations.types import CashflowOccurrence

AS_OF = date(2026, 7, 1)


def convert(amount: Decimal, currency: str) -> Decimal:
    rates = {"EUR": Decimal("1"), "PKR": Decimal("1") / Decimal("325")}
    return Decimal(amount) * rates[currency.upper()]


def _occ(day_offset, direction, amount, currency="EUR"):
    return CashflowOccurrence(
        due_date=AS_OF + timedelta(days=day_offset),
        direction=direction,
        amount=Decimal(amount),
        currency=currency,
    )


def test_projected_position_base_scenario():
    occ = [_occ(5, "inflow", "1000"), _occ(10, "outflow", "400")]
    p = projected_position(Decimal("500"), occ, convert, AS_OF, horizon_days=30)
    assert p.projected_inflows_base == Decimal("1000")
    assert p.projected_outflows_base == Decimal("400")
    assert p.projected_net_base == Decimal("1100")
    assert p.delta_base == Decimal("600")


def test_projected_position_scenario_multipliers_applied():
    occ = [_occ(5, "inflow", "1000"), _occ(10, "outflow", "1000")]
    cons = projected_position(Decimal("0"), occ, convert, AS_OF, 30, scenario="conservative")
    in_mult, out_mult = SCENARIOS["conservative"]
    assert cons.projected_inflows_base == Decimal("1000") * in_mult
    assert cons.projected_outflows_base == Decimal("1000") * out_mult


def test_projected_position_ignores_out_of_horizon():
    occ = [_occ(100, "inflow", "9999")]
    p = projected_position(Decimal("0"), occ, convert, AS_OF, horizon_days=30)
    assert p.projected_inflows_base == Decimal("0")


def test_daily_balance_series_tracks_minimum():
    occ = [_occ(3, "outflow", "800"), _occ(20, "inflow", "1000")]
    series = daily_balance_series(Decimal("500"), occ, convert, AS_OF, horizon_days=30)
    # Day 0..2: 500; day 3: -300 (minimum); recovers to 700 by day 20.
    assert series.minimum_balance_base == Decimal("-300")
    assert series.minimum_balance_day == AS_OF + timedelta(days=3)
    assert series.points[-1].balance_base == Decimal("700")
    assert len(series.points) == 31  # horizon_days + 1 inclusive


def test_daily_balance_currency_conversion():
    occ = [_occ(1, "outflow", "325", currency="PKR")]  # == 1 EUR
    series = daily_balance_series(Decimal("10"), occ, convert, AS_OF, horizon_days=5)
    assert series.points[1].balance_base == Decimal("9")
