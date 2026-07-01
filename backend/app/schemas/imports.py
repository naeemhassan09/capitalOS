"""Pydantic schemas for the CSV import subsystem."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ImportBatchOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    original_filename: str
    importer_type: str
    file_checksum: str
    status: str
    imported_row_count: int
    duplicate_row_count: int
    rejected_row_count: int
    error_report: dict | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ImporterInfo(BaseModel):
    importer_type: str
    display_name: str
    requires_column_map: bool


class PreviewRow(BaseModel):
    booking_date: date
    value_date: date | None = None
    description: str
    original_description: str
    amount: Decimal
    direction: str
    currency: str
    merchant: str | None = None
    external_id: str | None = None
    fingerprint: str
    is_duplicate: bool
    suggested_category_id: uuid.UUID | None = None
    suggested_kind: str


class RejectedRow(BaseModel):
    row_number: int
    reason: str
    raw: dict | None = None


class PreviewResponse(BaseModel):
    batch_id: uuid.UUID
    total: int
    duplicate_count: int
    new_count: int
    rejected_count: int
    columns: list[str]
    rows: list[PreviewRow]
    rejected: list[RejectedRow]


class ColumnMapRequest(BaseModel):
    """Optional column map supplied for generic imports (preview/commit)."""

    column_map: dict[str, str] | None = Field(default=None)


class CommitRequest(BaseModel):
    column_map: dict[str, str] | None = Field(default=None)
