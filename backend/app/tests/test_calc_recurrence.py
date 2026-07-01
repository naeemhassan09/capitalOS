"""Pure tests for expanding scheduled cashflows into dated occurrences."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.calculations.recurrence import ScheduledCashflowView, expand_occurrences


def _cf(**kw) -> ScheduledCashflowView:
    base = {
        "id": "cf", "name": "cf", "direction": "outflow", "amount": Decimal("100"),
        "currency": "EUR", "country": "IE", "first_due_date": date(2026, 7, 1),
    }
    base.update(kw)
    return ScheduledCashflowView(**base)


def test_one_off_within_window_produces_single_occurrence():
    cf = _cf(first_due_date=date(2026, 7, 15))
    occ = expand_occurrences([cf], date(2026, 7, 1), date(2026, 7, 31))
    assert len(occ) == 1
    assert occ[0].due_date == date(2026, 7, 15)


def test_one_off_outside_window_excluded():
    cf = _cf(first_due_date=date(2026, 9, 1))
    occ = expand_occurrences([cf], date(2026, 7, 1), date(2026, 7, 31))
    assert occ == []


def test_monthly_recurrence_count_limits_expansion():
    cf = _cf(first_due_date=date(2026, 6, 1),
             recurrence_rule="FREQ=MONTHLY;COUNT=3")
    occ = expand_occurrences([cf], date(2026, 1, 1), date(2026, 12, 31))
    assert len(occ) == 3
    assert [o.due_date for o in occ] == [date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1)]


def test_monthly_recurrence_bounded_by_window():
    cf = _cf(first_due_date=date(2026, 1, 1), recurrence_rule="FREQ=MONTHLY")
    occ = expand_occurrences([cf], date(2026, 3, 1), date(2026, 5, 31))
    # Mar, Apr, May only.
    assert [o.due_date for o in occ] == [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)]


def test_recurrence_respects_end_date():
    cf = _cf(first_due_date=date(2026, 1, 1), recurrence_rule="FREQ=MONTHLY",
             end_date=date(2026, 3, 15))
    occ = expand_occurrences([cf], date(2026, 1, 1), date(2026, 12, 31))
    assert [o.due_date for o in occ] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_cancelled_and_paid_statuses_skipped():
    cancelled = _cf(id="a", status="cancelled")
    paid = _cf(id="b", status="paid")
    active = _cf(id="c", status="planned")
    occ = expand_occurrences([cancelled, paid, active], date(2026, 7, 1), date(2026, 7, 31))
    assert len(occ) == 1


def test_occurrences_sorted_by_date_then_priority():
    a = _cf(id="a", first_due_date=date(2026, 7, 10), priority=50)
    b = _cf(id="b", first_due_date=date(2026, 7, 5), priority=10)
    c = _cf(id="c", first_due_date=date(2026, 7, 5), priority=90)
    occ = expand_occurrences([a, b, c], date(2026, 7, 1), date(2026, 7, 31))
    # Same date: higher priority first (sort key is -priority).
    assert [o.due_date for o in occ] == [date(2026, 7, 5), date(2026, 7, 5), date(2026, 7, 10)]
    assert occ[0].priority == 90
    assert occ[1].priority == 10
