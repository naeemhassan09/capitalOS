"""Investment holdings CRUD and valuation history."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.holding import Holding, ValuationHistory
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.holding import (
    HoldingCreate,
    HoldingOut,
    HoldingUpdate,
    ValuationCreate,
    ValuationOut,
)
from app.services.audit import log_event

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _to_out(holding: Holding) -> HoldingOut:
    gain_loss: Decimal | None = None
    if holding.cost_basis is not None:
        gain_loss = D(holding.latest_valuation) - D(holding.cost_basis)
    return HoldingOut.model_validate(holding).model_copy(update={"gain_loss": gain_loss})


@router.get("", response_model=list[HoldingOut])
def list_holdings(
    account_id: uuid.UUID | None = None,
    asset_class: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[HoldingOut]:
    stmt = select(Holding).where(Holding.user_id == user.id)
    if account_id is not None:
        stmt = stmt.where(Holding.account_id == account_id)
    if asset_class is not None:
        stmt = stmt.where(Holding.asset_class == asset_class)
    stmt = stmt.order_by(Holding.asset_name)
    return [_to_out(h) for h in db.scalars(stmt).all()]


@router.post("", response_model=HoldingOut, status_code=201)
def create_holding(
    payload: HoldingCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HoldingOut:
    holding = Holding(user_id=user.id, **payload.model_dump())
    db.add(holding)
    db.flush()
    log_event(db, action="holding.create", user_id=user.id, entity_type="holding",
              entity_id=holding.id, request=request, after={"asset_name": holding.asset_name})
    db.commit()
    db.refresh(holding)
    return _to_out(holding)


@router.get("/{holding_id}", response_model=HoldingOut)
def get_holding(
    holding_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HoldingOut:
    holding = get_owned_or_404(db, Holding, holding_id, user.id)
    return _to_out(holding)


@router.patch("/{holding_id}", response_model=HoldingOut)
def update_holding(
    holding_id: uuid.UUID,
    payload: HoldingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HoldingOut:
    holding = get_owned_or_404(db, Holding, holding_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(holding, key, value)
    log_event(db, action="holding.update", user_id=user.id, entity_type="holding",
              entity_id=holding.id, request=request)
    db.commit()
    db.refresh(holding)
    return _to_out(holding)


@router.delete("/{holding_id}", response_model=Message)
def delete_holding(
    holding_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    holding = get_owned_or_404(db, Holding, holding_id, user.id)
    db.delete(holding)
    log_event(db, action="holding.delete", user_id=user.id, entity_type="holding",
              entity_id=holding_id, request=request)
    db.commit()
    return Message(detail="Holding deleted")


@router.get("/{holding_id}/valuations", response_model=list[ValuationOut])
def list_valuations(
    holding_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ValuationHistory]:
    get_owned_or_404(db, Holding, holding_id, user.id)
    stmt = (
        select(ValuationHistory)
        .where(ValuationHistory.holding_id == holding_id)
        .order_by(ValuationHistory.valuation_date.desc())
    )
    return list(db.scalars(stmt).all())


@router.post("/{holding_id}/valuations", response_model=ValuationOut, status_code=201)
def add_valuation(
    holding_id: uuid.UUID,
    payload: ValuationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValuationHistory:
    holding = get_owned_or_404(db, Holding, holding_id, user.id)
    valuation = ValuationHistory(
        holding_id=holding.id,
        valuation_date=payload.valuation_date,
        valuation=payload.valuation,
        unit_price=payload.unit_price,
        source=payload.source,
    )
    db.add(valuation)
    # Keep the holding's headline figures in sync with the newest valuation.
    if holding.valuation_date is None or payload.valuation_date >= holding.valuation_date:
        holding.latest_valuation = payload.valuation
        holding.valuation_date = payload.valuation_date
        if payload.unit_price is not None:
            holding.latest_unit_price = payload.unit_price
    db.flush()
    log_event(db, action="holding.add_valuation", user_id=user.id, entity_type="holding",
              entity_id=holding.id, request=request,
              after={"valuation": str(payload.valuation)})
    db.commit()
    db.refresh(valuation)
    return valuation
