"""Deterministic categorisation rules, ordered by priority."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDPKMixin


class CategorisationRule(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "categorisation_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    match_field: Mapped[str] = mapped_column(String(32), nullable=False)
    operator: Mapped[str] = mapped_column(String(16), nullable=False)
    match_value: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_min: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    amount_max: Mapped[float | None] = mapped_column(MONEY, nullable=True)

    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    normalized_merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mark_as_transfer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mark_as_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    set_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
