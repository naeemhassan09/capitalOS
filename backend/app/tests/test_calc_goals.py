"""Pure tests for savings-goal funding math."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.calculations.goals import compute_goal_progress
from app.calculations.types import GoalView

AS_OF = date(2026, 7, 1)


def _goal(**kw) -> GoalView:
    base = {
        "id": "g", "name": "goal", "currency": "EUR",
        "target_amount": Decimal("1000"), "manual_contributed_amount": Decimal("0"),
    }
    base.update(kw)
    return GoalView(**base)


def test_manual_plus_linked_balances_is_current():
    g = _goal(manual_contributed_amount=Decimal("100"),
              linked_account_balances=[Decimal("250"), Decimal("150")])
    p = compute_goal_progress(g, AS_OF)
    assert p.current_amount == Decimal("500")
    assert p.remaining_amount == Decimal("500")
    assert p.percent_funded == Decimal("50")


def test_met_goal_caps_percent_and_remaining():
    g = _goal(target_amount=Decimal("1000"), manual_contributed_amount=Decimal("1200"))
    p = compute_goal_progress(g, AS_OF)
    assert p.status == "met"
    assert p.remaining_amount == Decimal("0")
    assert p.percent_funded == Decimal("100")
    assert p.on_track is True


def test_required_monthly_contribution_computed():
    # 60 days out -> 2 months; remaining 1000 -> 500/month.
    g = _goal(target_amount=Decimal("1000"), manual_contributed_amount=Decimal("0"),
              target_date=AS_OF + timedelta(days=60))
    p = compute_goal_progress(g, AS_OF)
    assert p.days_remaining == 60
    assert p.required_monthly_contribution == Decimal("500")


def test_min_one_month_floor_for_near_deadline():
    g = _goal(target_amount=Decimal("300"), manual_contributed_amount=Decimal("0"),
              target_date=AS_OF + timedelta(days=5))
    p = compute_goal_progress(g, AS_OF)
    # months clamps to 1 -> required == remaining.
    assert p.required_monthly_contribution == Decimal("300")


def test_past_deadline_unfunded_is_at_risk():
    g = _goal(target_amount=Decimal("1000"), manual_contributed_amount=Decimal("100"),
              target_date=AS_OF - timedelta(days=1))
    p = compute_goal_progress(g, AS_OF)
    assert p.days_remaining == -1
    assert p.on_track is False
    assert p.status == "at_risk"


def test_no_deadline_is_on_track():
    g = _goal(target_amount=Decimal("1000"), manual_contributed_amount=Decimal("10"))
    p = compute_goal_progress(g, AS_OF)
    assert p.days_remaining is None
    assert p.required_monthly_contribution is None
    assert p.on_track is True
    assert p.status == "active"
