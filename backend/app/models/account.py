"""Account model — banks, cards, cash, investments, property, liabilities."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDPKMixin


class Account(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    owner_member_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    account_subtype: Mapped[str | None] = mapped_column(String(48), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    country: Mapped[str] = mapped_column(String(8), default="IE", nullable=False)

    masked_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encrypted_iban: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    opening_balance: Mapped[float] = mapped_column(MONEY, default=0, nullable=False)
    current_balance: Mapped[float] = mapped_column(MONEY, default=0, nullable=False)
    balance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    credit_limit: Mapped[float | None] = mapped_column(MONEY, nullable=True)

    include_in_net_worth: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_in_liquid_assets: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_protected_reserve: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    account_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    transactions: Mapped[list[Transaction]] = relationship(  # noqa: F821
        back_populates="account",
        foreign_keys="Transaction.account_id",
        cascade="all, delete-orphan",
    )
