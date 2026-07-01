"""Reserve policies CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.reserve import ReservePolicy
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.reserve import ReserveCreate, ReserveOut, ReserveUpdate
from app.services.audit import log_event

router = APIRouter(prefix="/reserves", tags=["reserves"])


def _serialise_linked(linked: list[uuid.UUID] | None) -> list | None:
    return [str(a) for a in linked] if linked is not None else None


@router.get("", response_model=list[ReserveOut])
def list_reserves(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReservePolicy]:
    stmt = select(ReservePolicy).where(ReservePolicy.user_id == user.id)
    if not include_inactive:
        stmt = stmt.where(ReservePolicy.active.is_(True))
    stmt = stmt.order_by(ReservePolicy.name)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ReserveOut, status_code=201)
def create_reserve(
    payload: ReserveCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReservePolicy:
    data = payload.model_dump()
    data["linked_account_ids"] = _serialise_linked(data.get("linked_account_ids"))
    reserve = ReservePolicy(user_id=user.id, **data)
    db.add(reserve)
    db.flush()
    log_event(db, action="reserve.create", user_id=user.id, entity_type="reserve_policy",
              entity_id=reserve.id, request=request, after={"name": reserve.name})
    db.commit()
    db.refresh(reserve)
    return reserve


@router.get("/{reserve_id}", response_model=ReserveOut)
def get_reserve(
    reserve_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReservePolicy:
    return get_owned_or_404(db, ReservePolicy, reserve_id, user.id)


@router.patch("/{reserve_id}", response_model=ReserveOut)
def update_reserve(
    reserve_id: uuid.UUID,
    payload: ReserveUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReservePolicy:
    reserve = get_owned_or_404(db, ReservePolicy, reserve_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    if "linked_account_ids" in data:
        data["linked_account_ids"] = _serialise_linked(data["linked_account_ids"])
    for key, value in data.items():
        setattr(reserve, key, value)
    log_event(db, action="reserve.update", user_id=user.id, entity_type="reserve_policy",
              entity_id=reserve.id, request=request)
    db.commit()
    db.refresh(reserve)
    return reserve


@router.delete("/{reserve_id}", response_model=Message)
def delete_reserve(
    reserve_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    reserve = get_owned_or_404(db, ReservePolicy, reserve_id, user.id)
    db.delete(reserve)
    log_event(db, action="reserve.delete", user_id=user.id, entity_type="reserve_policy",
              entity_id=reserve_id, request=request)
    db.commit()
    return Message(detail="Reserve policy deleted")
