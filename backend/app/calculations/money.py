"""Decimal money helpers. Never use binary floating point for money."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
ZERO = Decimal("0")


def D(value: object) -> Decimal:
    """Coerce anything sane into a Decimal without float rounding artefacts."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def money(value: object) -> Decimal:
    """Quantize to 2 dp for display/settlement amounts."""
    return D(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def dsum(values: Iterable[object]) -> Decimal:
    total = ZERO
    for v in values:
        total += D(v)
    return total
