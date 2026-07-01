"""Category schemas (hierarchical)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CategoryBase(BaseModel):
    parent_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = None  # auto-derived from name when omitted
    icon: str | None = None
    color: str | None = None
    is_essential: bool = False
    is_income: bool = False
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    parent_id: uuid.UUID | None = None
    name: str | None = None
    slug: str | None = None
    icon: str | None = None
    color: str | None = None
    is_essential: bool | None = None
    is_income: bool | None = None
    sort_order: int | None = None


class CategoryOut(ORMModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    slug: str
    icon: str | None
    color: str | None
    is_essential: bool
    is_system: bool
    is_income: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    children: list[CategoryOut] = []


CategoryOut.model_rebuild()
