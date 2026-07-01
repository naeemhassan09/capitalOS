"""Exchange rates with source provenance and manual override support."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import RATE, Base, UUIDPKMixin


class ExchangeRate(UUIDPKMixin, Base):
    __tablename__ = "exchange_rates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[float] = mapped_column(RATE, nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_fx_user_pair_date",
            "user_id",
            "base_currency",
            "quote_currency",
            "rate_date",
            unique=True,
        ),
    )
