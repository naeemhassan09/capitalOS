"""Pure tests for the authoritative deployable-capital formula (spec §6.5/§19).

    deployable = liquid_assets - current_liabilities
                 - committed_future_expenses(horizon)
                 - protected_reserves - minimum_operating_cash
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.calculations.positions import deployable_capital
from app.calculations.types import (
    AccountView,
    CashflowOccurrence,
    HoldingView,
    ReserveView,
)

AS_OF = date(2026, 7, 1)


def make_converter(rates: dict[str, Decimal]):
    def convert(amount: Decimal, currency: str) -> Decimal:
        return Decimal(amount) * rates[currency.upper()]

    return convert


EUR_ONLY = make_converter({"EUR": Decimal("1"), "PKR": Decimal("1") / Decimal("325")})


def _acc(**kw) -> AccountView:
    base = {
        "id": "a", "name": "acc", "currency": "EUR", "country": "IE",
        "account_type": "current", "balance": Decimal("0"),
    }
    base.update(kw)
    return AccountView(**base)


def test_reserves_and_committed_expenses_reduce_deployable():
    """Big gross assets, yet deployable is negative after reserves + commitments."""
    accounts = [
        _acc(id="1", balance=Decimal("10000")),  # healthy cash
        _acc(id="2", account_type="credit_card", balance=Decimal("-2000")),
    ]
    holdings: list[HoldingView] = []
    reserves = [
        ReserveView(id="r", name="floor", currency="EUR", jurisdiction="IE",
                    protected_amount=Decimal("7000")),
    ]
    occurrences = [
        CashflowOccurrence(due_date=AS_OF + timedelta(days=5), direction="outflow",
                           amount=Decimal("1500"), currency="EUR", country="IE"),
        CashflowOccurrence(due_date=AS_OF + timedelta(days=10), direction="outflow",
                           amount=Decimal("600"), currency="EUR", country="IE"),
    ]
    res = deployable_capital(accounts, holdings, reserves, occurrences, EUR_ONLY,
                             as_of=AS_OF, horizon_days=30)
    # liquid 10000 - liabilities 2000 - committed 2100 - reserves 7000 = -1100
    assert res.liquid_assets_base == Decimal("10000")
    assert res.current_liabilities_base == Decimal("2000")
    assert res.committed_expenses_base == Decimal("2100")
    assert res.protected_reserves_base == Decimal("7000")
    assert res.total_base == Decimal("-1100")
    assert res.total_base < 0


def test_min_operating_cash_subtracted():
    accounts = [_acc(id="1", balance=Decimal("5000"))]
    res = deployable_capital(accounts, [], [], [], EUR_ONLY, as_of=AS_OF,
                             horizon_days=30, min_operating_cash=Decimal("1000"))
    assert res.total_base == Decimal("4000")


def test_committed_expenses_only_within_horizon():
    accounts = [_acc(id="1", balance=Decimal("5000"))]
    occurrences = [
        CashflowOccurrence(due_date=AS_OF + timedelta(days=5), direction="outflow",
                           amount=Decimal("500"), currency="EUR"),
        CashflowOccurrence(due_date=AS_OF + timedelta(days=100), direction="outflow",
                           amount=Decimal("9999"), currency="EUR"),  # beyond horizon
    ]
    res = deployable_capital(accounts, [], [], occurrences, EUR_ONLY, as_of=AS_OF,
                             horizon_days=30)
    assert res.committed_expenses_base == Decimal("500")
    assert res.total_base == Decimal("4500")


def test_inflows_are_not_treated_as_committed_expenses():
    accounts = [_acc(id="1", balance=Decimal("1000"))]
    occurrences = [
        CashflowOccurrence(due_date=AS_OF + timedelta(days=3), direction="inflow",
                           amount=Decimal("5000"), currency="EUR"),
    ]
    res = deployable_capital(accounts, [], [], occurrences, EUR_ONLY, as_of=AS_OF,
                             horizon_days=30)
    assert res.committed_expenses_base == Decimal("0")


def test_jurisdiction_split_keeps_ie_and_pk_separate():
    accounts = [
        _acc(id="ie", country="IE", currency="EUR", balance=Decimal("3000")),
        _acc(id="pk", country="PK", currency="PKR", balance=Decimal("650000")),
    ]
    reserves = [
        ReserveView(id="r-pk", name="family", currency="PKR", jurisdiction="PK",
                    protected_amount=Decimal("325000")),
    ]
    occurrences = [
        CashflowOccurrence(due_date=AS_OF + timedelta(days=2), direction="outflow",
                           amount=Decimal("650"), currency="EUR", country="IE"),
        CashflowOccurrence(due_date=AS_OF + timedelta(days=2), direction="outflow",
                           amount=Decimal("325000"), currency="PKR", country="PK"),
    ]
    res = deployable_capital(accounts, [], reserves, occurrences, EUR_ONLY,
                             as_of=AS_OF, horizon_days=30)
    by = {j.country: j for j in res.by_jurisdiction}
    assert set(by) == {"IE", "PK"}
    # IE: liquid 3000 - committed 650 = 2350 (no reserve)
    assert by["IE"].deployable_base == Decimal("2350")
    # PK: liquid 2000 (650000/325) - committed 1000 - reserves 1000 = 0
    assert by["PK"].liquid_base == Decimal("2000")
    assert by["PK"].deployable_base == Decimal("0")


def test_fx_converter_is_injected_not_hardcoded():
    """Same inputs with different rate tables must give different results — proof
    that nothing FX-related is hard-coded inside the calculation layer."""
    accounts = [_acc(id="pk", country="PK", currency="PKR", balance=Decimal("325000"))]
    strong = make_converter({"PKR": Decimal("1") / Decimal("325")})   # 325/EUR
    weak = make_converter({"PKR": Decimal("1") / Decimal("400")})     # 400/EUR

    res_strong = deployable_capital(accounts, [], [], [], strong, as_of=AS_OF)
    res_weak = deployable_capital(accounts, [], [], [], weak, as_of=AS_OF)

    assert res_strong.total_base == Decimal("1000")
    assert res_weak.total_base == Decimal("812.50")
    assert res_strong.total_base != res_weak.total_base


def test_horizon_default_is_thirty_days():
    accounts = [_acc(id="1", balance=Decimal("100"))]
    res = deployable_capital(accounts, [], [], [], EUR_ONLY, as_of=AS_OF)
    assert res.horizon_days == 30
