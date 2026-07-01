"""Dashboard and cashflow-forecast endpoints."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.calculations.positions import settled_position
from app.calculations.projections import SCENARIOS, daily_balance_series
from app.calculations.recurrence import expand_occurrences
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.providers.fx import FxError, ManualFxProvider
from app.schemas.dashboard import CashflowForecastOut, DashboardOut
from app.services.dashboard import build_dashboard
from app.services.views import load_account_views, load_scheduled_views

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ALLOWED_HORIZONS = {7, 30, 60, 90}


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return build_dashboard(db, user)


@router.get("/cashflow", response_model=CashflowForecastOut)
def get_cashflow_forecast(
    scenario: str = Query("base"),
    horizon: int = Query(30),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    as_of = date.today()
    base_currency = user.base_currency

    scenario = scenario if scenario in SCENARIOS else "base"
    horizon = horizon if horizon in ALLOWED_HORIZONS else 30

    warnings: list[dict] = []
    missing_pairs: set[tuple[str, str]] = set()

    try:
        convert = ManualFxProvider(db, user.id).converter(base_currency)
    except FxError:
        warnings.append(
            {
                "level": "warning",
                "code": "fx_unavailable",
                "message": "No exchange rates configured; values shown at par.",
            }
        )

        def convert(amount, currency):  # type: ignore[misc]
            return D(amount)

    def safe_convert(amount, currency):
        try:
            return convert(D(amount), currency)
        except FxError:
            missing_pairs.add((currency.upper(), base_currency.upper()))
            return D(amount)

    accounts = load_account_views(db, user.id)
    scheduled = load_scheduled_views(db, user.id)

    settled = settled_position(accounts, safe_convert)

    target = as_of + timedelta(days=horizon)
    occurrences = expand_occurrences(scheduled, as_of, target)

    series = daily_balance_series(
        starting_net_base=settled.net_base,
        occurrences=occurrences,
        convert=safe_convert,
        as_of=as_of,
        horizon_days=horizon,
        scenario=scenario,
    )

    points = [
        {
            "day": p.day,
            "balance_base": p.balance_base,
            "inflow_base": p.inflow_base,
            "outflow_base": p.outflow_base,
        }
        for p in series.points
    ]

    obligations = [
        {
            "name": o.name,
            "due_date": o.due_date,
            "amount": D(o.amount),
            "currency": o.currency,
            "base_amount": safe_convert(D(o.amount), o.currency),
            "country": o.country,
        }
        for o in occurrences
        if o.direction == "outflow" and as_of <= o.due_date <= target
    ]
    obligations.sort(key=lambda x: (x["due_date"], x["name"]))

    if series.minimum_balance_base < 0:
        warnings.append(
            {
                "level": "danger",
                "code": "negative_projected_balance",
                "message": (
                    f"Projected balance goes negative "
                    f"({series.minimum_balance_base}) on "
                    f"{series.minimum_balance_day}."
                ),
            }
        )

    for frm, to in sorted(missing_pairs):
        warnings.append(
            {
                "level": "warning",
                "code": "fx_rate_missing",
                "message": f"Missing exchange rate {frm}->{to}; value shown at par.",
            }
        )

    return {
        "scenario": scenario,
        "horizon_days": horizon,
        "as_of": as_of,
        "base_currency": base_currency,
        "starting_net_base": series.starting_net_base,
        "minimum_balance_base": series.minimum_balance_base,
        "minimum_balance_day": series.minimum_balance_day,
        "points": points,
        "obligations": obligations,
        "warnings": warnings,
    }
