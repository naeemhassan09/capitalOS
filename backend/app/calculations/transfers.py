"""Transfer matching between two accounts (possibly cross-currency)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.calculations.money import ZERO, D
from app.calculations.types import Converter


@dataclass(frozen=True)
class TransferCandidate:
    id: str
    account_id: str
    booking_date: date
    amount: Decimal  # positive magnitude
    currency: str
    direction: str  # credit | debit
    description: str = ""


@dataclass
class TransferMatch:
    debit_id: str
    credit_id: str
    confidence: Decimal
    fx_implied: bool


def _base(amount: Decimal, currency: str, convert: Converter) -> Decimal:
    return convert(D(amount), currency)


def propose_transfer_matches(
    candidates: list[TransferCandidate],
    convert: Converter,
    max_days_apart: int = 3,
    tolerance: Decimal = Decimal("0.02"),
) -> list[TransferMatch]:
    """Pair debits with credits on different accounts whose base-currency values
    are within ``tolerance`` (fractional) and dates within ``max_days_apart``.
    """
    debits = [c for c in candidates if c.direction == "debit"]
    credits = [c for c in candidates if c.direction == "credit"]
    used_credits: set[str] = set()
    matches: list[TransferMatch] = []

    for d in sorted(debits, key=lambda c: c.booking_date):
        d_base = _base(d.amount, d.currency, convert)
        best: TransferCandidate | None = None
        best_score = Decimal("-1")
        for c in credits:
            if c.id in used_credits or c.account_id == d.account_id:
                continue
            days = abs((c.booking_date - d.booking_date).days)
            if days > max_days_apart:
                continue
            c_base = _base(c.amount, c.currency, convert)
            if d_base <= 0:
                continue
            diff = abs(d_base - c_base) / d_base
            if diff > tolerance:
                continue
            # Score: closeness in value and date (higher is better).
            value_score = Decimal(1) - diff
            date_score = Decimal(1) - (Decimal(days) / Decimal(max_days_apart + 1))
            score = value_score * Decimal("0.7") + date_score * Decimal("0.3")
            if score > best_score:
                best_score = score
                best = c
        if best is not None:
            used_credits.add(best.id)
            matches.append(
                TransferMatch(
                    debit_id=d.id,
                    credit_id=best.id,
                    confidence=best_score if best_score > ZERO else ZERO,
                    fx_implied=best.currency != d.currency,
                )
            )
    return matches
