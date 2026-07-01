"""Reserve policies — protected funds that are not deployable capital."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDPKMixin


class ReservePolicy(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "reserve_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(8), default="IE", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    target_amount: Mapped[float] = mapped_column(MONEY, default=0, nullable=False)
    protected_amount: Mapped[float] = mapped_column(MONEY, default=0, nullable=False)
    hard_floor: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    preferred_target: Mapped[float | None] = mapped_column(MONEY, nullable=True)

    months_of_coverage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_expense_basis: Mapped[float | None] = mapped_column(MONEY, nullable=True)

    linked_account_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
