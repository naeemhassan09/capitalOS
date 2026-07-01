"""User and server-side session models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Dublin", nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="en-IE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # TOTP fields modelled now; the enable/verify flow is deferred (see README).
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    encrypted_totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(UUIDPKMixin, Base):
    """Server-side session, enabling revocation and 'active sessions' listing."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
