"""Open-banking connections (Enable Banking) and their account links.

Sensitive provider identifiers — the API session id and the external account
uids — are encrypted at rest with the application Fernet key and are never
exposed through the API.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class BankConnection(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "bank_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    provider: Mapped[str] = mapped_column(String(32), default="enable_banking", nullable=False)
    aspsp_name: Mapped[str] = mapped_column(String(120), nullable=False)
    aspsp_country: Mapped[str] = mapped_column(String(8), nullable=False)

    # Random uuid used to correlate the bank redirect back to this row.
    state: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    encrypted_session_id: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # pending | active | expired | revoked
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    links: Mapped[list[BankAccountLink]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class BankAccountLink(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "bank_account_links"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("bank_connections.id", ondelete="CASCADE"),
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )

    encrypted_external_uid: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # Last 4 characters of whatever identifier the bank exposes (IBAN, masked
    # PAN, ...) — cards have no IBAN, so this never assumes one exists.
    identifier_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connection: Mapped[BankConnection] = relationship(back_populates="links")
