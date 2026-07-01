"""Hierarchical transaction categories."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Category(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_essential: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    children: Mapped[list[Category]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped[Category | None] = relationship(
        back_populates="children", remote_side="Category.id"
    )
