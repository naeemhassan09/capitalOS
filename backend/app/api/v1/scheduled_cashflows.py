"""Scheduled cashflows CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.scheduled_cashflow import ScheduledCashflow
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.scheduled_cashflow import (
    ScheduledCashflowCreate,
    ScheduledCashflowOut,
    ScheduledCashflowUpdate,
)
from app.services.audit import log_event

router = APIRouter(prefix="/scheduled-cashflows", tags=["scheduled-cashflows"])


@router.get("", response_model=list[ScheduledCashflowOut])
def list_cashflows(
    status: str | None = None,
    direction: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScheduledCashflow]:
    stmt = select(ScheduledCashflow).where(ScheduledCashflow.user_id == user.id)
    if status is not None:
        stmt = stmt.where(ScheduledCashflow.status == status)
    if direction is not None:
        stmt = stmt.where(ScheduledCashflow.direction == direction)
    stmt = stmt.order_by(ScheduledCashflow.next_due_date, ScheduledCashflow.priority)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ScheduledCashflowOut, status_code=201)
def create_cashflow(
    payload: ScheduledCashflowCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledCashflow:
    data = payload.model_dump()
    if data.get("next_due_date") is None:
        data["next_due_date"] = data["first_due_date"]
    cashflow = ScheduledCashflow(user_id=user.id, **data)
    db.add(cashflow)
    db.flush()
    log_event(db, action="scheduled_cashflow.create", user_id=user.id,
              entity_type="scheduled_cashflow", entity_id=cashflow.id, request=request,
              after={"name": cashflow.name})
    db.commit()
    db.refresh(cashflow)
    return cashflow


@router.get("/{cashflow_id}", response_model=ScheduledCashflowOut)
def get_cashflow(
    cashflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledCashflow:
    return get_owned_or_404(db, ScheduledCashflow, cashflow_id, user.id)


@router.patch("/{cashflow_id}", response_model=ScheduledCashflowOut)
def update_cashflow(
    cashflow_id: uuid.UUID,
    payload: ScheduledCashflowUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledCashflow:
    cashflow = get_owned_or_404(db, ScheduledCashflow, cashflow_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cashflow, key, value)
    log_event(db, action="scheduled_cashflow.update", user_id=user.id,
              entity_type="scheduled_cashflow", entity_id=cashflow.id, request=request)
    db.commit()
    db.refresh(cashflow)
    return cashflow


@router.delete("/{cashflow_id}", response_model=Message)
def delete_cashflow(
    cashflow_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    cashflow = get_owned_or_404(db, ScheduledCashflow, cashflow_id, user.id)
    db.delete(cashflow)
    log_event(db, action="scheduled_cashflow.delete", user_id=user.id,
              entity_type="scheduled_cashflow", entity_id=cashflow_id, request=request)
    db.commit()
    return Message(detail="Scheduled cashflow deleted")
