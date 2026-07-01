"""Expand scheduled cash flows into concrete dated occurrences."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from dateutil.rrule import rrulestr

from app.calculations.money import D
from app.calculations.types import CashflowOccurrence

# Statuses that should not generate future obligations.
INACTIVE_STATUSES = {"cancelled", "paid"}


@dataclass(frozen=True)
class ScheduledCashflowView:
    id: str
    name: str
    direction: str  # inflow | outflow
    amount: Decimal
    currency: str
    country: str
    first_due_date: date
    recurrence_rule: str | None = None
    end_date: date | None = None
    priority: int = 100
    status: str = "planned"


def _to_date(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def expand_occurrences(
    cashflows: Iterable[ScheduledCashflowView],
    start: date,
    end: date,
    max_per_rule: int = 500,
) -> list[CashflowOccurrence]:
    """Return every occurrence with ``start <= due_date <= end`` (inclusive)."""
    occurrences: list[CashflowOccurrence] = []
    for cf in cashflows:
        if cf.status in INACTIVE_STATUSES:
            continue
        dates: list[date] = []
        if cf.recurrence_rule:
            dtstart = datetime.combine(cf.first_due_date, datetime.min.time())
            rule = rrulestr(cf.recurrence_rule, dtstart=dtstart)
            hard_end = min(end, cf.end_date) if cf.end_date else end
            for dt in rule:
                d = _to_date(dt)
                if d > hard_end:
                    break
                if d >= start:
                    dates.append(d)
                if len(dates) >= max_per_rule:
                    break
        else:
            if start <= cf.first_due_date <= end and (
                cf.end_date is None or cf.first_due_date <= cf.end_date
            ):
                dates.append(cf.first_due_date)

        for d in dates:
            occurrences.append(
                CashflowOccurrence(
                    due_date=d,
                    direction=cf.direction,
                    amount=D(cf.amount),
                    currency=cf.currency,
                    country=cf.country,
                    name=cf.name,
                    priority=cf.priority,
                )
            )
    occurrences.sort(key=lambda o: (o.due_date, -o.priority))
    return occurrences
