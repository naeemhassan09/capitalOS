"""Spending analytics. Transfers, card repayments and investing are excluded."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.calculations.money import ZERO, D
from app.calculations.types import Converter

# Kinds that represent genuine consumption.
SPENDING_KINDS = {"expense", "fee", "interest"}
REFUND_KINDS = {"refund"}
INCOME_KINDS = {"income", "investment_sale"}
EXCLUDED_STATUSES = {"reversed", "excluded"}


@dataclass(frozen=True)
class TransactionView:
    amount: Decimal  # positive magnitude
    currency: str
    kind: str
    status: str
    booking_date: date
    is_transfer: bool = False
    category_id: str | None = None
    category_name: str = "Uncategorised"
    account_id: str | None = None
    account_name: str = ""
    country: str = "OTHER"
    member: str = "self"
    is_essential: bool = False


def _is_spending(t: TransactionView) -> bool:
    return (
        not t.is_transfer
        and t.status not in EXCLUDED_STATUSES
        and t.kind in SPENDING_KINDS
    )


def _is_refund(t: TransactionView) -> bool:
    return (
        not t.is_transfer
        and t.status not in EXCLUDED_STATUSES
        and t.kind in REFUND_KINDS
    )


def net_spending(txns: Iterable[TransactionView], convert: Converter) -> Decimal:
    total = ZERO
    for t in txns:
        if _is_spending(t):
            total += convert(D(t.amount), t.currency)
        elif _is_refund(t):
            total -= convert(D(t.amount), t.currency)
    return total


def total_income(txns: Iterable[TransactionView], convert: Converter) -> Decimal:
    return sum(
        (
            convert(D(t.amount), t.currency)
            for t in txns
            if t.kind in INCOME_KINDS and t.status not in EXCLUDED_STATUSES and not t.is_transfer
        ),
        ZERO,
    )


def _grouped(txns: Iterable[TransactionView], convert: Converter, key) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for t in txns:
        if _is_spending(t):
            k = key(t)
            out[k] = out.get(k, ZERO) + convert(D(t.amount), t.currency)
        elif _is_refund(t):
            k = key(t)
            out[k] = out.get(k, ZERO) - convert(D(t.amount), t.currency)
    return out


def spending_by_category(txns, convert: Converter) -> dict[str, Decimal]:
    return _grouped(txns, convert, lambda t: t.category_name)


def spending_by_account(txns, convert: Converter) -> dict[str, Decimal]:
    return _grouped(txns, convert, lambda t: t.account_name or t.account_id or "unknown")


def spending_by_country(txns, convert: Converter) -> dict[str, Decimal]:
    return _grouped(txns, convert, lambda t: t.country)


def spending_by_member(txns, convert: Converter) -> dict[str, Decimal]:
    return _grouped(txns, convert, lambda t: t.member)


def essential_vs_discretionary(txns, convert: Converter) -> dict[str, Decimal]:
    essential = ZERO
    discretionary = ZERO
    for t in txns:
        if not _is_spending(t):
            continue
        base = convert(D(t.amount), t.currency)
        if t.is_essential:
            essential += base
        else:
            discretionary += base
    return {"essential": essential, "discretionary": discretionary}


def savings_rate(income_base: Decimal, spending_base: Decimal) -> Decimal:
    """Fraction of income not spent, clamped to [-1, 1] range sensibly."""
    if income_base <= 0:
        return ZERO
    return (income_base - spending_base) / income_base
