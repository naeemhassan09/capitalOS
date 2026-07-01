"""Household member schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class HouseholdMemberBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relationship_type: str = "self"
    can_login: bool = False
    linked_user_id: uuid.UUID | None = None


class HouseholdMemberCreate(HouseholdMemberBase):
    pass


class HouseholdMemberUpdate(BaseModel):
    name: str | None = None
    relationship_type: str | None = None
    can_login: bool | None = None
    linked_user_id: uuid.UUID | None = None


class HouseholdMemberOut(ORMModel):
    id: uuid.UUID
    name: str
    relationship_type: str
    can_login: bool
    linked_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
