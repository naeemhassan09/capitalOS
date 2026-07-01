"""Pure tests for settled positions, liquid assets, net worth and reserves."""

from __future__ import annotations

from decimal import Decimal

from app.calculations.positions import (
    current_liabilities,
    liquid_assets,
    net_worth,
    protected_reserves_total,
    settled_position,
)
from app.calculations.types import AccountView, HoldingView, ReserveView

# A stub converter: rate table maps currency -> value of 1 unit in base (EUR).
RATES = {
    "EUR": Decimal("1"),
    "PKR": Decimal("1") / Decimal("325"),  # 325 PKR = 1 EUR
    "USD": Decimal("0.9"),
    "GBP": Decimal("1.15"),
    "SAR": Decimal("0.24"),
}


def convert(amount: Decimal, currency: str) -> Decimal:
    return Decimal(amount) * RATES[currency.upper()]


def _acc(**kw) -> AccountView:
    base = {
        "id": "a", "name": "acc", "currency": "EUR", "country": "IE",
        "account_type": "current", "balance": Decimal("0"),
    }
    base.update(kw)
    return AccountView(**base)


def test_settled_position_signs():
    accounts = [
        _acc(id="1", balance=Decimal("1000")),
        _acc(id="2", account_type="credit_card", balance=Decimal("-300")),
    ]
    pos = settled_position(accounts, convert)
    assert pos.assets_base == Decimal("1000")
    assert pos.liabilities_base == Decimal("300")
    assert pos.net_base == Decimal("700")


def test_settled_position_excludes_out_of_net_worth_and_archived():
    accounts = [
        _acc(id="1", balance=Decimal("1000")),
        _acc(id="2", balance=Decimal("500"), include_in_net_worth=False),
        _acc(id="3", balance=Decimal("500"), is_archived=True),
    ]
    pos = settled_position(accounts, convert)
    assert pos.net_base == Decimal("1000")


def test_liquid_assets_only_positive_immediate_and_holdings():
    accounts = [
        _acc(id="1", balance=Decimal("1000")),  # counts
        _acc(id="2", account_type="credit_card", balance=Decimal("-300")),  # liability, skip
        _acc(id="3", balance=Decimal("50"), include_in_liquid_assets=False),  # skip
    ]
    holdings = [
        HoldingView(id="h1", asset_name="mf", asset_class="mutual_fund",
                    native_currency="EUR", valuation=Decimal("200"),
                    liquidity_class="immediate"),
        HoldingView(id="h2", asset_name="pension", asset_class="pension",
                    native_currency="EUR", valuation=Decimal("999"),
                    liquidity_class="restricted"),  # not immediate, skip
    ]
    assert liquid_assets(accounts, holdings, convert) == Decimal("1200")


def test_current_liabilities_sum_of_negative_balances():
    accounts = [
        _acc(id="1", balance=Decimal("1000")),
        _acc(id="2", account_type="credit_card", balance=Decimal("-117")),
        _acc(id="3", account_type="loan", balance=Decimal("-883")),
    ]
    assert current_liabilities(accounts, convert) == Decimal("1000")


def test_protected_reserves_total_converts_currency():
    reserves = [
        ReserveView(id="r1", name="IE", currency="EUR", jurisdiction="IE",
                    protected_amount=Decimal("2000")),
        ReserveView(id="r2", name="PK", currency="PKR", jurisdiction="PK",
                    protected_amount=Decimal("325000")),
    ]
    # 325,000 PKR / 325 = 1000 EUR; + 2000 EUR = 3000 EUR.
    assert protected_reserves_total(reserves, convert) == Decimal("3000")


def test_net_worth_property_and_pension_split():
    accounts = [_acc(id="1", balance=Decimal("1000"))]
    holdings = [
        HoldingView(id="h1", asset_name="stock", asset_class="stock",
                    native_currency="EUR", valuation=Decimal("500")),
        HoldingView(id="h2", asset_name="pension", asset_class="pension",
                    native_currency="EUR", valuation=Decimal("300"),
                    liquidity_class="restricted"),
        HoldingView(id="h3", asset_name="plot", asset_class="property",
                    native_currency="EUR", valuation=Decimal("10000"),
                    liquidity_class="illiquid"),
    ]
    reserves: list[ReserveView] = []
    nw = net_worth(accounts, holdings, reserves, convert)
    # financial ex-property = accounts (1000) + stock (500) + pension (300) = 1800
    assert nw.financial_ex_property_base == Decimal("1800")
    assert nw.total_net_worth_base == Decimal("11800")
    assert nw.retirement_assets_base == Decimal("300")
