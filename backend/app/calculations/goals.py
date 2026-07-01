"""Savings-goal funding calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.calculations.money import ZERO, D
from app.calculations.types import GoalView


@dataclass
class GoalProgress:
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


def compute_goal_progress(goal: GoalView, as_of: date) -> GoalProgress:
    linked = sum((D(b) for b in goal.linked_account_balances), ZERO)
    current = D(goal.manual_contributed_amount) + linked
    target = D(goal.target_amount)
    remaining = target - current
    if remaining < 0:
        remaining = ZERO

    percent = ZERO
    if target > 0:
        percent = (current / target) * Decimal(100)
        if percent > Decimal(100):
            percent = Decimal(100)

    days_remaining: int | None = None
    required_monthly: Decimal | None = None
    if goal.target_date is not None:
        days_remaining = (goal.target_date - as_of).days
        if remaining > 0 and days_remaining and days_remaining > 0:
            months = Decimal(days_remaining) / Decimal(30)
            if months < 1:
                months = Decimal(1)
            required_monthly = remaining / months

    met = current >= target and target > 0
    # On track if fully funded, or no deadline, or deadline not yet passed.
    on_track = met or days_remaining is None or days_remaining >= 0
    status = "met" if met else ("at_risk" if not on_track else "active")

    return GoalProgress(
        id=goal.id,
        name=goal.name,
        currency=goal.currency,
        target_amount=target,
        current_amount=current,
        remaining_amount=remaining,
        percent_funded=percent,
        days_remaining=days_remaining,
        required_monthly_contribution=required_monthly,
        on_track=on_track,
        status=status,
    )
