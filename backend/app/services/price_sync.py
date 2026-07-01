"""Sync external market prices into the user's holdings.

Rules:
- Only holdings with a ``ticker`` set and ``quantity > 0`` are priced; the
  rest are skipped (their valuations stay manual).
- A successful fetch updates the holding's headline figures
  (``latest_unit_price``, ``latest_valuation``, ``valuation_date``) and marks
  ``valuation_is_manual = False``.
- One ValuationHistory row per holding per day: today's auto row is updated
  in place if it already exists, so repeated syncs don't pile up history.
- Per-holding failures are collected and reported, never fatal for the run.
- The fetched price is assumed to be quoted in the holding's native currency.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.models.holding import Holding, ValuationHistory
from app.models.user import User
from app.providers.prices import PriceError, fetch_price

logger = logging.getLogger("capitalos.prices")


def sync_user_prices(db: Session, user: User) -> dict:
    """Fetch market prices for the user's tickered holdings and upsert them."""
    holdings = db.scalars(
        select(Holding).where(Holding.user_id == user.id).order_by(Holding.asset_name)
    ).all()
    today = date.today()

    updated: list[dict] = []
    skipped: list[str] = []
    errors: list[dict] = []
    for holding in holdings:
        ticker = (holding.ticker or "").strip()
        quantity = D(holding.quantity)
        if not ticker or quantity <= 0:
            skipped.append(holding.asset_name)
            continue
        try:
            price, source = fetch_price(ticker)
        except PriceError as exc:
            errors.append({"name": holding.asset_name, "error": str(exc)})
            continue

        valuation = quantity * price
        holding.latest_unit_price = price
        holding.latest_valuation = valuation
        holding.valuation_date = today
        holding.valuation_is_manual = False

        existing = db.scalar(
            select(ValuationHistory).where(
                ValuationHistory.holding_id == holding.id,
                ValuationHistory.valuation_date == today,
            )
        )
        if existing is not None:
            existing.unit_price = price
            existing.valuation = valuation
            existing.source = source
        else:
            db.add(
                ValuationHistory(
                    holding_id=holding.id,
                    valuation_date=today,
                    unit_price=price,
                    valuation=valuation,
                    source=source,
                )
            )
        updated.append(
            {
                "asset_name": holding.asset_name,
                "ticker": ticker,
                "price": price,
                "valuation": valuation,
            }
        )
    db.commit()
    return {"updated": updated, "skipped": skipped, "errors": errors}


def sync_all_users(db: Session) -> None:
    """Best-effort price sync for every active user (used by the daily scheduler)."""
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    for user in users:
        try:
            result = sync_user_prices(db, user)
            if result["updated"] or result["errors"]:
                logger.info(
                    "Prices synced for %s: %d updated, %d skipped, %d errors",
                    user.email,
                    len(result["updated"]),
                    len(result["skipped"]),
                    len(result["errors"]),
                )
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected price sync error for %s", user.email)
            db.rollback()
