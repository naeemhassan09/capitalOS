"""Household members CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.household import HouseholdMember
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.household import (
    HouseholdMemberCreate,
    HouseholdMemberOut,
    HouseholdMemberUpdate,
)
from app.services.audit import log_event

router = APIRouter(prefix="/household", tags=["household"])


@router.get("", response_model=list[HouseholdMemberOut])
def list_members(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[HouseholdMember]:
    stmt = (
        select(HouseholdMember)
        .where(HouseholdMember.user_id == user.id)
        .order_by(HouseholdMember.name)
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=HouseholdMemberOut, status_code=201)
def create_member(
    payload: HouseholdMemberCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HouseholdMember:
    member = HouseholdMember(user_id=user.id, **payload.model_dump())
    db.add(member)
    db.flush()
    log_event(db, action="household.create", user_id=user.id, entity_type="household_member",
              entity_id=member.id, request=request, after={"name": member.name})
    db.commit()
    db.refresh(member)
    return member


@router.get("/{member_id}", response_model=HouseholdMemberOut)
def get_member(
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HouseholdMember:
    return get_owned_or_404(db, HouseholdMember, member_id, user.id)


@router.patch("/{member_id}", response_model=HouseholdMemberOut)
def update_member(
    member_id: uuid.UUID,
    payload: HouseholdMemberUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HouseholdMember:
    member = get_owned_or_404(db, HouseholdMember, member_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, key, value)
    log_event(db, action="household.update", user_id=user.id, entity_type="household_member",
              entity_id=member.id, request=request)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", response_model=Message)
def delete_member(
    member_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    member = get_owned_or_404(db, HouseholdMember, member_id, user.id)
    db.delete(member)
    log_event(db, action="household.delete", user_id=user.id, entity_type="household_member",
              entity_id=member_id, request=request)
    db.commit()
    return Message(detail="Household member deleted")
