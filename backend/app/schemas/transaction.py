"""Transaction schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    booking_date: date
    value_date: date | None = None
    description: str = Field(default="", max_length=500)
    original_description: str | None = None
    merchant: str | None = None
    counterparty: str | None = None
    amount: Decimal  # positive magnitude
    currency: str = Field(min_length=3, max_length=3)
    direction: str  # credit | debit
    kind: str = "expense"
    status: str = "booked"
    category_id: uuid.UUID | None = None
    notes: str | None = None
    external_transaction_id: str | None = None
    is_reviewed: bool = False


class TransactionUpdate(BaseModel):
    booking_date: date | None = None
    value_date: date | None = None
    description: str | None = None
    merchant: str | None = None
    counterparty: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    direction: str | None = None
    kind: str | None = None
    status: str | None = None
    category_id: uuid.UUID | None = None
    notes: str | None = None
    is_reviewed: bool | None = None


class TransactionOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    linked_account_id: uuid.UUID | None
    import_batch_id: uuid.UUID | None
    external_transaction_id: str | None
    fingerprint: str
    booking_date: date
    value_date: date | None
    description: str
    original_description: str | None
    merchant: str | None
    counterparty: str | None
    amount: Decimal
    currency: str
    base_currency_amount: Decimal | None
    exchange_rate: Decimal | None
    direction: str
    kind: str
    status: str
    category_id: uuid.UUID | None
    notes: str | None
    is_transfer: bool
    transfer_group_id: uuid.UUID | None
    is_recurring: bool
    is_reviewed: bool
    source: str
    created_at: datetime
    updated_at: datetime


class BulkCategorise(BaseModel):
    ids: list[uuid.UUID]
    category_id: uuid.UUID | None = None
    mark_reviewed: bool = False


class BulkReview(BaseModel):
    ids: list[uuid.UUID]
    is_reviewed: bool


class BulkResult(BaseModel):
    updated: int


class TransferLink(BaseModel):
    debit_id: uuid.UUID
    credit_id: uuid.UUID


class TransferCreate(BaseModel):
    """Create both legs of an internal transfer in one call (double entry)."""

    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    to_amount: Decimal | None = None  # for cross-currency; defaults to amount
    booking_date: date
    description: str | None = None
    category_id: uuid.UUID | None = None


class TransferLinkResult(BaseModel):
    group_id: uuid.UUID


class TransferCandidateSide(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    booking_date: date
    amount: Decimal
    currency: str
    direction: str
    description: str


class TransferCandidateOut(BaseModel):
    debit: TransferCandidateSide
    credit: TransferCandidateSide
    confidence: Decimal
    fx_implied: bool
