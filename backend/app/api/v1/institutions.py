"""Institutions CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.institution import Institution
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.institution import (
    InstitutionCreate,
    InstitutionOut,
    InstitutionUpdate,
)
from app.services.audit import log_event

router = APIRouter(prefix="/institutions", tags=["institutions"])


@router.get("", response_model=list[InstitutionOut])
def list_institutions(
    country: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Institution]:
    stmt = select(Institution).where(Institution.user_id == user.id)
    if country:
        stmt = stmt.where(Institution.country == country)
    if not include_inactive:
        stmt = stmt.where(Institution.is_active.is_(True))
    stmt = stmt.order_by(Institution.country, Institution.name)
    return list(db.scalars(stmt).all())


@router.post("", response_model=InstitutionOut, status_code=201)
def create_institution(
    payload: InstitutionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Institution:
    institution = Institution(user_id=user.id, **payload.model_dump())
    db.add(institution)
    db.flush()
    log_event(db, action="institution.create", user_id=user.id, entity_type="institution",
              entity_id=institution.id, request=request, after={"name": institution.name})
    db.commit()
    db.refresh(institution)
    return institution


@router.get("/{institution_id}", response_model=InstitutionOut)
def get_institution(
    institution_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Institution:
    return get_owned_or_404(db, Institution, institution_id, user.id)


@router.patch("/{institution_id}", response_model=InstitutionOut)
def update_institution(
    institution_id: uuid.UUID,
    payload: InstitutionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Institution:
    institution = get_owned_or_404(db, Institution, institution_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(institution, key, value)
    log_event(db, action="institution.update", user_id=user.id, entity_type="institution",
              entity_id=institution.id, request=request)
    db.commit()
    db.refresh(institution)
    return institution


@router.delete("/{institution_id}", response_model=Message)
def delete_institution(
    institution_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    institution = get_owned_or_404(db, Institution, institution_id, user.id)
    db.delete(institution)
    log_event(db, action="institution.delete", user_id=user.id, entity_type="institution",
              entity_id=institution_id, request=request)
    db.commit()
    return Message(detail="Institution deleted")
