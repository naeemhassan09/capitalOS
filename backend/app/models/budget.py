"""Monthly per-category budgets (limits in the user's base currency)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDPKMixin


class Budget(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "budgets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE")
    )
    # Monthly limit, expressed in the user's base currency.
    amount: Mapped[float] = mapped_column(MONEY, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        # One budget per category per user.
        Index("uq_budget_user_category", "user_id", "category_id", unique=True),
    )
