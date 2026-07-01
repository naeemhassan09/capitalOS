"""Pure tests for transfer matching (including cross-currency)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.calculations.transfers import TransferCandidate, propose_transfer_matches

DAY = date(2026, 6, 10)


def convert(amount: Decimal, currency: str) -> Decimal:
    rates = {"EUR": Decimal("1"), "PKR": Decimal("1") / Decimal("325")}
    return Decimal(amount) * rates[currency.upper()]


def _c(id, account, direction, amount, day_offset=0, currency="EUR"):
    return TransferCandidate(
        id=id, account_id=account, booking_date=DAY + timedelta(days=day_offset),
        amount=Decimal(amount), currency=currency, direction=direction,
    )


def test_matches_same_currency_within_tolerance_and_dates():
    cands = [
        _c("d1", "A", "debit", "100"),
        _c("c1", "B", "credit", "100", day_offset=1),
    ]
    matches = propose_transfer_matches(cands, convert)
    assert len(matches) == 1
    assert matches[0].debit_id == "d1"
    assert matches[0].credit_id == "c1"
    assert matches[0].fx_implied is False
    assert matches[0].confidence > 0


def test_does_not_match_same_account():
    cands = [
        _c("d1", "A", "debit", "100"),
        _c("c1", "A", "credit", "100"),
    ]
    assert propose_transfer_matches(cands, convert) == []


def test_does_not_match_beyond_date_window():
    cands = [
        _c("d1", "A", "debit", "100"),
        _c("c1", "B", "credit", "100", day_offset=10),
    ]
    assert propose_transfer_matches(cands, convert, max_days_apart=3) == []


def test_does_not_match_outside_value_tolerance():
    cands = [
        _c("d1", "A", "debit", "100"),
        _c("c1", "B", "credit", "150"),  # 50% off, well beyond 2%
    ]
    assert propose_transfer_matches(cands, convert) == []


def test_cross_currency_match_flags_fx_implied():
    # 100 EUR debit, 32500 PKR credit == 100 EUR in base.
    cands = [
        _c("d1", "A", "debit", "100", currency="EUR"),
        _c("c1", "B", "credit", "32500", currency="PKR", day_offset=1),
    ]
    matches = propose_transfer_matches(cands, convert)
    assert len(matches) == 1
    assert matches[0].fx_implied is True


def test_each_credit_used_once():
    cands = [
        _c("d1", "A", "debit", "100"),
        _c("d2", "A", "debit", "100", day_offset=1),
        _c("c1", "B", "credit", "100"),
    ]
    matches = propose_transfer_matches(cands, convert)
    assert len(matches) == 1  # only one credit available
