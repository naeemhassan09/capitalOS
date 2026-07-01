"""Exchange rates CRUD, upsert and currency conversion."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.providers.fx import FxError, ManualFxProvider
from app.providers.fx_external import ExternalFxError
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.exchange_rate import (
    ConversionResult,
    ExchangeRateCreate,
    ExchangeRateOut,
    ExchangeRateUpdate,
    FxSyncResult,
)
from app.services.audit import log_event
from app.services.fx_sync import sync_user_rates

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])


@router.get("", response_model=list[ExchangeRateOut])
def list_rates(
    base: str | None = None,
    quote: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ExchangeRate]:
    stmt = select(ExchangeRate).where(ExchangeRate.user_id == user.id)
    if base:
        stmt = stmt.where(ExchangeRate.base_currency == base.upper())
    if quote:
        stmt = stmt.where(ExchangeRate.quote_currency == quote.upper())
    stmt = stmt.order_by(
        ExchangeRate.base_currency,
        ExchangeRate.quote_currency,
        ExchangeRate.rate_date.desc(),
    )
    return list(db.scalars(stmt).all())


@router.get("/convert", response_model=ConversionResult)
def convert(
    amount: Decimal = Query(...),
    from_currency: str = Query(..., alias="from", min_length=3, max_length=3),
    to_currency: str = Query(..., alias="to", min_length=3, max_length=3),
    on_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversionResult:
    """Convert an amount between two currencies using the user's rate graph."""
    provider = ManualFxProvider(db, user.id)
    frm = from_currency.upper()
    to = to_currency.upper()
    try:
        rate = provider.get_rate(frm, to, on_date)
    except FxError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ConversionResult(
        amount=amount,
        from_currency=frm,
        to_currency=to,
        on_date=on_date,
        converted=amount * rate,
    )


@router.post("/sync", response_model=FxSyncResult)
def sync_rates(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FxSyncResult:
    """Fetch today's market rates from a free external source and store them.

    Manual rates entered for today are never overwritten; historical rows are
    never touched.
    """
    try:
        result = sync_user_rates(db, user)
    except ExternalFxError as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not fetch external rates: {exc}"
        ) from exc
    log_event(db, action="exchange_rate.sync", user_id=user.id,
              entity_type="exchange_rate", request=request,
              after={"updated": result["updated"], "source": result["source"]})
    db.commit()
    return FxSyncResult(**result)


@router.post("", response_model=ExchangeRateOut, status_code=201)
def upsert_rate(
    payload: ExchangeRateCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExchangeRate:
    base = payload.base_currency.upper()
    quote = payload.quote_currency.upper()
    existing = db.scalar(
        select(ExchangeRate).where(
            ExchangeRate.user_id == user.id,
            ExchangeRate.base_currency == base,
            ExchangeRate.quote_currency == quote,
            ExchangeRate.rate_date == payload.rate_date,
        )
    )
    if existing is not None:
        existing.rate = payload.rate
        existing.source = payload.source
        existing.is_manual = payload.is_manual
        log_event(db, action="exchange_rate.update", user_id=user.id,
                  entity_type="exchange_rate", entity_id=existing.id, request=request)
        db.commit()
        db.refresh(existing)
        return existing

    rate = ExchangeRate(
        user_id=user.id,
        base_currency=base,
        quote_currency=quote,
        rate=payload.rate,
        rate_date=payload.rate_date,
        source=payload.source,
        is_manual=payload.is_manual,
    )
    db.add(rate)
    db.flush()
    log_event(db, action="exchange_rate.create", user_id=user.id,
              entity_type="exchange_rate", entity_id=rate.id, request=request,
              after={"pair": f"{base}/{quote}"})
    db.commit()
    db.refresh(rate)
    return rate


@router.get("/{rate_id}", response_model=ExchangeRateOut)
def get_rate(
    rate_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExchangeRate:
    return get_owned_or_404(db, ExchangeRate, rate_id, user.id)


@router.patch("/{rate_id}", response_model=ExchangeRateOut)
def update_rate(
    rate_id: uuid.UUID,
    payload: ExchangeRateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExchangeRate:
    rate = get_owned_or_404(db, ExchangeRate, rate_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rate, key, value)
    log_event(db, action="exchange_rate.update", user_id=user.id,
              entity_type="exchange_rate", entity_id=rate.id, request=request)
    db.commit()
    db.refresh(rate)
    return rate


@router.delete("/{rate_id}", response_model=Message)
def delete_rate(
    rate_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    rate = get_owned_or_404(db, ExchangeRate, rate_id, user.id)
    db.delete(rate)
    log_event(db, action="exchange_rate.delete", user_id=user.id,
              entity_type="exchange_rate", entity_id=rate_id, request=request)
    db.commit()
    return Message(detail="Exchange rate deleted")
