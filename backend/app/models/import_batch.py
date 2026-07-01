"""Import batch tracking for CSV ingestion and rollback."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class ImportBatch(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    importer_type: Mapped[str] = mapped_column(String(32), nullable=False)

    imported_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(24), default="uploaded", nullable=False)
    error_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
