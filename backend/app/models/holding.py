"""Investment holdings and valuation history."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, RATE, Base, TimestampMixin, UUIDPKMixin


class Holding(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "holdings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    asset_name: Mapped[str] = mapped_column(String(160), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(48), nullable=True)
    asset_class: Mapped[str] = mapped_column(String(32), default="other", nullable=False)

    quantity: Mapped[float] = mapped_column(RATE, default=0, nullable=False)
    native_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cost_basis: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    latest_unit_price: Mapped[float | None] = mapped_column(RATE, nullable=True)
    latest_valuation: Mapped[float] = mapped_column(MONEY, default=0, nullable=False)
    valuation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    liquidity_class: Mapped[str] = mapped_column(String(16), default="immediate", nullable=False)
    include_in_net_worth: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valuation_is_manual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    valuations: Mapped[list[ValuationHistory]] = relationship(
        back_populates="holding", cascade="all, delete-orphan"
    )


class ValuationHistory(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "valuation_history"

    holding_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("holdings.id", ondelete="CASCADE"), index=True
    )
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(RATE, nullable=True)
    valuation: Mapped[float] = mapped_column(MONEY, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)

    holding: Mapped[Holding] = relationship(back_populates="valuations")
