"""Transaction model — the core ledger entry."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, RATE, Base, TimestampMixin, UUIDPKMixin


class Transaction(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )

    external_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint_version: Mapped[int] = mapped_column(default=1, nullable=False)

    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    original_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)

    amount: Mapped[float] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    base_currency_amount: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    exchange_rate: Mapped[float | None] = mapped_column(RATE, nullable=True)

    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="expense", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="booked", nullable=False)

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    account: Mapped[Account] = relationship(  # noqa: F821
        back_populates="transactions", foreign_keys=[account_id]
    )

    __table_args__ = (
        # A given account should never ingest the same fingerprint twice.
        Index("uq_txn_account_fingerprint", "account_id", "fingerprint", unique=True),
        Index("ix_txn_account_booking_date", "account_id", "booking_date"),
        Index("ix_txn_external_id", "external_transaction_id"),
        Index("ix_txn_import_batch", "import_batch_id"),
        Index("ix_txn_category", "category_id"),
        Index("ix_txn_transfer_group", "transfer_group_id"),
    )
