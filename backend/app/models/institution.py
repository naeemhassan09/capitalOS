"""Financial institution model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Institution(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "institutions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(8), default="IE", nullable=False)
    institution_type: Mapped[str] = mapped_column(String(48), default="bank", nullable=False)
    logo_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    open_banking_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
