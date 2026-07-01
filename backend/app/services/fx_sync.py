"""Sync external FX rates into the user's exchange_rates table.

Rules:
- Rates are stored as (base = user's base currency) -> quote rows for today,
  with ``is_manual = False`` and the source name; the rate graph triangulates
  any cross pair from these.
- A MANUAL rate for the same (pair, date) is never overwritten — user override
  always wins for that day.
- Historical rows are never touched, so past conversions are preserved.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Currency
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.providers.fx_external import ExternalFxError, fetch_latest_rates

logger = logging.getLogger("capitalos.fx")


def sync_user_rates(db: Session, user: User) -> dict:
    """Fetch today's rates for all supported currencies and upsert them."""
    base = user.base_currency.upper()
    symbols = [c.value for c in Currency if c.value != base]
    rates, source = fetch_latest_rates(base, symbols)  # may raise ExternalFxError
    today = date.today()

    updated: list[str] = []
    skipped_manual: list[str] = []
    for quote, rate in rates.items():
        existing = db.scalar(
            select(ExchangeRate).where(
                ExchangeRate.user_id == user.id,
                ExchangeRate.base_currency == base,
                ExchangeRate.quote_currency == quote,
                ExchangeRate.rate_date == today,
            )
        )
        if existing is not None:
            if existing.is_manual:
                skipped_manual.append(quote)
                continue
            existing.rate = rate
            existing.source = source
        else:
            db.add(
                ExchangeRate(
                    user_id=user.id,
                    base_currency=base,
                    quote_currency=quote,
                    rate=rate,
                    rate_date=today,
                    source=source,
                    is_manual=False,
                )
            )
        updated.append(quote)
    db.commit()
    return {
        "base_currency": base,
        "rate_date": today,
        "source": source,
        "updated": sorted(updated),
        "skipped_manual": sorted(skipped_manual),
        "rates": {q: rates[q] for q in sorted(rates)},
    }


def sync_all_users(db: Session) -> None:
    """Best-effort sync for every active user (used by the daily scheduler)."""
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    for user in users:
        try:
            result = sync_user_rates(db, user)
            logger.info(
                "FX synced for %s: %s from %s",
                user.email, ",".join(result["updated"]), result["source"],
            )
        except ExternalFxError as exc:
            logger.warning("FX sync failed for %s: %s", user.email, exc)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected FX sync error for %s", user.email)
            db.rollback()
