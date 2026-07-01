"""Balance-sheet calculations: settled position, liquidity, reserves,
true deployable capital and net worth.

Sign convention: account balances are signed — assets positive, liabilities
negative — so a credit card owing 117 has ``balance = -117``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.calculations.money import ZERO, D
from app.calculations.types import (
    AccountView,
    CashflowOccurrence,
    Converter,
    HoldingView,
    ReserveView,
)

DEFAULT_LIQUID_LIQUIDITY = {"immediate"}


# --------------------------------------------------------------------- results
@dataclass
class SettledPosition:
    assets_base: Decimal
    liabilities_base: Decimal
    net_base: Decimal


@dataclass
class JurisdictionDeployable:
    country: str
    liquid_base: Decimal
    liabilities_base: Decimal
    committed_expenses_base: Decimal
    protected_reserves_base: Decimal
    min_operating_cash_base: Decimal
    deployable_base: Decimal


@dataclass
class DeployableResult:
    as_of: date
    horizon_days: int
    liquid_assets_base: Decimal
    current_liabilities_base: Decimal
    committed_expenses_base: Decimal
    protected_reserves_base: Decimal
    min_operating_cash_base: Decimal
    total_base: Decimal
    by_jurisdiction: list[JurisdictionDeployable] = field(default_factory=list)


@dataclass
class NetWorth:
    liquid_net_worth_base: Decimal
    financial_ex_property_base: Decimal
    total_net_worth_base: Decimal
    retirement_assets_base: Decimal
    protected_reserves_base: Decimal
    investable_assets_base: Decimal
    liabilities_base: Decimal


# ---------------------------------------------------------------- primitives
def _active(accounts: Iterable[AccountView]) -> list[AccountView]:
    return [a for a in accounts if not a.is_archived]


def settled_position(accounts: Iterable[AccountView], convert: Converter) -> SettledPosition:
    assets = ZERO
    liabilities = ZERO
    for a in _active(accounts):
        if not a.include_in_net_worth:
            continue
        base = convert(D(a.balance), a.currency)
        if base >= 0:
            assets += base
        else:
            liabilities += -base
    return SettledPosition(assets, liabilities, assets - liabilities)


def liquid_assets(
    accounts: Iterable[AccountView],
    holdings: Iterable[HoldingView],
    convert: Converter,
    liquidity_classes: set[str] = DEFAULT_LIQUID_LIQUIDITY,
) -> Decimal:
    total = ZERO
    for a in _active(accounts):
        if not a.include_in_liquid_assets or a.is_liability:
            continue
        bal = D(a.balance)
        if bal > 0:
            total += convert(bal, a.currency)
    for h in holdings:
        if h.include_in_net_worth and h.liquidity_class in liquidity_classes:
            total += convert(D(h.valuation), h.native_currency)
    return total


def current_liabilities(accounts: Iterable[AccountView], convert: Converter) -> Decimal:
    total = ZERO
    for a in _active(accounts):
        bal = D(a.balance)
        if bal < 0:
            total += convert(-bal, a.currency)
    return total


def protected_reserves_total(reserves: Iterable[ReserveView], convert: Converter) -> Decimal:
    return sum((convert(D(r.protected_amount), r.currency) for r in reserves), ZERO)


def protected_reserves_by_currency(reserves: Iterable[ReserveView]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for r in reserves:
        out[r.currency] = out.get(r.currency, ZERO) + D(r.protected_amount)
    return out


def committed_expenses(
    occurrences: Iterable[CashflowOccurrence],
    convert: Converter,
    start: date,
    end: date,
    country: str | None = None,
) -> Decimal:
    total = ZERO
    for o in occurrences:
        if o.direction != "outflow":
            continue
        if not (start <= o.due_date <= end):
            continue
        if country is not None and o.country != country:
            continue
        total += convert(D(o.amount), o.currency)
    return total


# ------------------------------------------------------- deployable capital
def deployable_capital(
    accounts: Sequence[AccountView],
    holdings: Sequence[HoldingView],
    reserves: Sequence[ReserveView],
    occurrences: Sequence[CashflowOccurrence],
    convert: Converter,
    as_of: date,
    horizon_days: int = 30,
    min_operating_cash: Decimal = ZERO,
    liquidity_classes: set[str] = DEFAULT_LIQUID_LIQUIDITY,
) -> DeployableResult:
    """Authoritative formula (spec §6.5):

        deployable = liquid_assets - current_liabilities
                     - committed_future_expenses(horizon)
                     - protected_reserves - minimum_operating_cash
    """
    end = as_of + timedelta(days=horizon_days)

    liq = liquid_assets(accounts, holdings, convert, liquidity_classes)
    liab = current_liabilities(accounts, convert)
    committed = committed_expenses(occurrences, convert, as_of, end)
    reserves_total = protected_reserves_total(reserves, convert)
    total = liq - liab - committed - reserves_total - min_operating_cash

    by_jurisdiction: list[JurisdictionDeployable] = []
    countries = sorted({a.country for a in accounts} | {r.jurisdiction for r in reserves})
    for country in countries:
        c_accounts = [a for a in accounts if a.country == country]
        c_holdings = [h for h in holdings if h.country == country]
        c_reserves = [r for r in reserves if r.jurisdiction == country]
        c_liq = liquid_assets(c_accounts, c_holdings, convert, liquidity_classes)
        c_liab = current_liabilities(c_accounts, convert)
        c_committed = committed_expenses(occurrences, convert, as_of, end, country=country)
        c_reserves_total = protected_reserves_total(c_reserves, convert)
        c_deploy = c_liq - c_liab - c_committed - c_reserves_total
        by_jurisdiction.append(
            JurisdictionDeployable(
                country=country,
                liquid_base=c_liq,
                liabilities_base=c_liab,
                committed_expenses_base=c_committed,
                protected_reserves_base=c_reserves_total,
                min_operating_cash_base=ZERO,
                deployable_base=c_deploy,
            )
        )

    return DeployableResult(
        as_of=as_of,
        horizon_days=horizon_days,
        liquid_assets_base=liq,
        current_liabilities_base=liab,
        committed_expenses_base=committed,
        protected_reserves_base=reserves_total,
        min_operating_cash_base=min_operating_cash,
        total_base=total,
        by_jurisdiction=by_jurisdiction,
    )


# ------------------------------------------------------------------ net worth
def net_worth(
    accounts: Sequence[AccountView],
    holdings: Sequence[HoldingView],
    reserves: Sequence[ReserveView],
    convert: Converter,
    liquidity_classes: set[str] = DEFAULT_LIQUID_LIQUIDITY,
) -> NetWorth:
    liq = liquid_assets(accounts, holdings, convert, liquidity_classes)
    liab = current_liabilities(accounts, convert)

    account_net = ZERO
    for a in _active(accounts):
        if a.include_in_net_worth:
            account_net += convert(D(a.balance), a.currency)

    holdings_ex_property = ZERO
    property_value = ZERO
    retirement = ZERO
    for h in holdings:
        if not h.include_in_net_worth:
            continue
        v = convert(D(h.valuation), h.native_currency)
        if h.asset_class == "property":
            property_value += v
        else:
            holdings_ex_property += v
        if h.asset_class == "pension":
            retirement += v

    financial_ex_property = account_net + holdings_ex_property
    total = financial_ex_property + property_value
    reserves_total = protected_reserves_total(reserves, convert)
    # Investable = liquid money not locked behind reserves.
    investable = liq - reserves_total

    return NetWorth(
        liquid_net_worth_base=liq - liab,
        financial_ex_property_base=financial_ex_property,
        total_net_worth_base=total,
        retirement_assets_base=retirement,
        protected_reserves_base=reserves_total,
        investable_assets_base=investable,
        liabilities_base=liab,
    )


def currency_exposure(
    accounts: Sequence[AccountView],
    holdings: Sequence[HoldingView],
    convert: Converter,
) -> dict[str, Decimal]:
    """Base-currency value of assets grouped by their native currency."""
    out: dict[str, Decimal] = {}
    for a in _active(accounts):
        bal = D(a.balance)
        if bal > 0 and a.include_in_net_worth:
            out[a.currency] = out.get(a.currency, ZERO) + convert(bal, a.currency)
    for h in holdings:
        if h.include_in_net_worth:
            out[h.native_currency] = out.get(h.native_currency, ZERO) + convert(
                D(h.valuation), h.native_currency
            )
    return out
