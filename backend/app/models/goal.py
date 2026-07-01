"""Savings goals."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDPKMixin


class SavingsGoal(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "savings_goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_amount: Mapped[float] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    goal_type: Mapped[str] = mapped_column(String(32), default="custom", nullable=False)

    # Optional explicit account links; JSON list of account UUIDs (as strings).
    linked_account_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    manual_contributed_amount: Mapped[float] = mapped_column(MONEY, default=0, nullable=False)

    protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
