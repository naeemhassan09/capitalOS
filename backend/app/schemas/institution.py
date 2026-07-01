"""Institution schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class InstitutionBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    country: str = "IE"
    institution_type: str = "bank"
    logo_identifier: str | None = None
    website: str | None = None
    open_banking_provider: str | None = None
    is_active: bool = True


class InstitutionCreate(InstitutionBase):
    pass


class InstitutionUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    institution_type: str | None = None
    logo_identifier: str | None = None
    website: str | None = None
    open_banking_provider: str | None = None
    is_active: bool | None = None


class InstitutionOut(ORMModel):
    id: uuid.UUID
    name: str
    country: str
    institution_type: str
    logo_identifier: str | None
    website: str | None
    open_banking_provider: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
