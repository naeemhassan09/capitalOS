"""Scheduled (recurring/one-off) future income and expenses."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDPKMixin


class ScheduledCashflow(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_cashflows"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # inflow|outflow
    amount: Mapped[float] = mapped_column(MONEY, nullable=False)  # always positive magnitude
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    first_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    # RFC 5545 RRULE string, e.g. "FREQ=MONTHLY;BYMONTHDAY=28". Empty = one-off.
    recurrence_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    occurrence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="planned", nullable=False)
    auto_match: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
