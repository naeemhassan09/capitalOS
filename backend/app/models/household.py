"""Household member model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class HouseholdMember(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "household_members"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), default="self", nullable=False)
    can_login: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    linked_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
