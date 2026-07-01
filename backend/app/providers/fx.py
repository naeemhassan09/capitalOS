"""Foreign-exchange providers and rate resolution.

An ``ExchangeRate`` row means: ``1 base_currency = rate quote_currency`` on
``rate_date``. Conversion between arbitrary currencies is resolved by building a
directed graph of the latest known rates and finding a shortest multiplicative
path (supports triangulation, e.g. USD→PKR→EUR).
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import date
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.models.exchange_rate import ExchangeRate


class FxError(RuntimeError):
    """Raised when a rate cannot be resolved between two currencies."""


class FxProvider(Protocol):
    def get_rate(
        self, from_currency: str, to_currency: str, on_date: date | None = None
    ) -> Decimal:
        ...


class RateGraph:
    """Immutable directed graph of currency conversion factors."""

    def __init__(self, edges: dict[str, dict[str, Decimal]]):
        self._edges = edges

    def rate(self, frm: str, to: str) -> Decimal:
        frm, to = frm.upper(), to.upper()
        if frm == to:
            return Decimal(1)
        # BFS for the fewest-hop path; multiply factors along the way.
        seen = {frm}
        queue: deque[tuple[str, Decimal]] = deque([(frm, Decimal(1))])
        while queue:
            node, factor = queue.popleft()
            for nxt, w in self._edges.get(node, {}).items():
                if nxt == to:
                    return factor * w
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, factor * w))
        raise FxError(f"No exchange rate path from {frm} to {to}")


class ManualFxProvider:
    """Resolves rates from user-maintained ``exchange_rates`` rows."""

    def __init__(self, db: Session, user_id: uuid.UUID):
        self._db = db
        self._user_id = user_id

    def _latest_rows(self, on_date: date | None) -> list[ExchangeRate]:
        stmt = select(ExchangeRate).where(ExchangeRate.user_id == self._user_id)
        if on_date is not None:
            stmt = stmt.where(ExchangeRate.rate_date <= on_date)
        stmt = stmt.order_by(ExchangeRate.rate_date.desc())
        rows = list(self._db.scalars(stmt).all())
        # Keep only the most recent row per (base, quote) pair.
        latest: dict[tuple[str, str], ExchangeRate] = {}
        for r in rows:
            key = (r.base_currency.upper(), r.quote_currency.upper())
            if key not in latest:
                latest[key] = r
        return list(latest.values())

    def build_graph(self, on_date: date | None = None) -> RateGraph:
        edges: dict[str, dict[str, Decimal]] = {}
        for r in self._latest_rows(on_date):
            rate = D(r.rate)
            if rate <= 0:
                continue
            b, q = r.base_currency.upper(), r.quote_currency.upper()
            edges.setdefault(b, {})[q] = rate
            edges.setdefault(q, {}).setdefault(b, Decimal(1) / rate)
        return RateGraph(edges)

    def get_rate(
        self, from_currency: str, to_currency: str, on_date: date | None = None
    ) -> Decimal:
        return self.build_graph(on_date).rate(from_currency, to_currency)

    def converter(self, base_currency: str, on_date: date | None = None):
        graph = self.build_graph(on_date)
        base = base_currency.upper()

        def convert(amount: Decimal, currency: str) -> Decimal:
            return D(amount) * graph.rate(currency.upper(), base)

        return convert
