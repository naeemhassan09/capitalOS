"""Pure tests for spending analytics.

Transfers, credit-card repayments and investment purchases must NOT be counted
as spending (spec §19).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.calculations.spending import (
    TransactionView,
    essential_vs_discretionary,
    net_spending,
    savings_rate,
    spending_by_category,
    spending_by_country,
    total_income,
)

DAY = date(2026, 6, 15)


def convert(amount: Decimal, currency: str) -> Decimal:
    rates = {"EUR": Decimal("1"), "PKR": Decimal("1") / Decimal("325")}
    return Decimal(amount) * rates[currency.upper()]


def _t(**kw) -> TransactionView:
    base = {
        "amount": Decimal("0"), "currency": "EUR", "kind": "expense", "status": "booked",
        "booking_date": DAY,
    }
    base.update(kw)
    return TransactionView(**base)


def test_net_spending_counts_expenses_fees_interest():
    txns = [
        _t(amount=Decimal("100"), kind="expense"),
        _t(amount=Decimal("5"), kind="fee"),
        _t(amount=Decimal("3"), kind="interest"),
    ]
    assert net_spending(txns, convert) == Decimal("108")


def test_credit_card_payment_excluded_from_spending():
    txns = [
        _t(amount=Decimal("100"), kind="expense"),
        _t(amount=Decimal("500"), kind="credit_card_payment"),
    ]
    assert net_spending(txns, convert) == Decimal("100")


def test_internal_transfer_excluded_from_spending():
    txns = [
        _t(amount=Decimal("100"), kind="expense"),
        _t(amount=Decimal("900"), kind="internal_transfer", is_transfer=True),
        # Even a normal expense flagged as a transfer must not count.
        _t(amount=Decimal("50"), kind="expense", is_transfer=True),
    ]
    assert net_spending(txns, convert) == Decimal("100")


def test_investment_purchase_and_opening_balance_excluded():
    txns = [
        _t(amount=Decimal("100"), kind="expense"),
        _t(amount=Decimal("2000"), kind="investment_purchase"),
        _t(amount=Decimal("5000"), kind="opening_balance"),
    ]
    assert net_spending(txns, convert) == Decimal("100")


def test_refunds_reduce_net_spending():
    txns = [
        _t(amount=Decimal("100"), kind="expense"),
        _t(amount=Decimal("30"), kind="refund"),
    ]
    assert net_spending(txns, convert) == Decimal("70")


def test_excluded_and_reversed_statuses_ignored():
    txns = [
        _t(amount=Decimal("100"), kind="expense"),
        _t(amount=Decimal("999"), kind="expense", status="reversed"),
        _t(amount=Decimal("999"), kind="expense", status="excluded"),
    ]
    assert net_spending(txns, convert) == Decimal("100")


def test_total_income_excludes_transfers():
    txns = [
        _t(amount=Decimal("3200"), kind="income"),
        _t(amount=Decimal("50"), kind="investment_sale"),
        _t(amount=Decimal("999"), kind="income", is_transfer=True),
    ]
    assert total_income(txns, convert) == Decimal("3250")


def test_spending_by_category_and_country_with_fx():
    txns = [
        _t(amount=Decimal("100"), kind="expense", category_name="Food", country="IE"),
        _t(amount=Decimal("325"), kind="expense", category_name="Family",
           country="PK", currency="PKR"),
    ]
    by_cat = spending_by_category(txns, convert)
    assert by_cat["Food"] == Decimal("100")
    assert by_cat["Family"] == Decimal("1")  # 325 PKR / 325
    by_country = spending_by_country(txns, convert)
    assert by_country["IE"] == Decimal("100")
    assert by_country["PK"] == Decimal("1")


def test_essential_vs_discretionary():
    txns = [
        _t(amount=Decimal("100"), kind="expense", is_essential=True),
        _t(amount=Decimal("40"), kind="expense", is_essential=False),
    ]
    split = essential_vs_discretionary(txns, convert)
    assert split["essential"] == Decimal("100")
    assert split["discretionary"] == Decimal("40")


def test_savings_rate_clamped_and_zero_income():
    assert savings_rate(Decimal("1000"), Decimal("750")) == Decimal("0.25")
    assert savings_rate(Decimal("0"), Decimal("100")) == Decimal("0")
