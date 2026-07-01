"""CSV import orchestration: upload, preview, commit and rollback.

Storage & safety
----------------
Uploaded bytes are stored under ``settings.upload_dir`` in a per-user subdir,
optionally encrypted at rest with the app's Fernet key. Uploaded content is
*never* executed or evaluated — it is only ever read as CSV text via pandas.

Duplicate detection
--------------------
Duplicates are decided solely by the versioned :func:`build_fingerprint`
(account + date + amount + currency + normalized description + external id).
Re-importing an identical file therefore yields zero new rows, independent of
filename, row order or upload timestamp.
"""

from __future__ import annotations

import base64
import hashlib
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.core.config import settings
from app.core.security import decrypt_str, encrypt_str
from app.importers import (
    IMPORTER_REGISTRY,
    BaseTransactionImporter,
    ImporterError,
    ParsedRow,
)
from app.models.account import Account
from app.models.import_batch import ImportBatch
from app.models.transaction import Transaction
from app.services.transactions import (
    FINGERPRINT_VERSION,
    apply_rules,
    build_fingerprint,
    load_rules,
)

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]")
_PREVIEW_LIMIT = 100

# Marker prepended to encrypted-at-rest payloads so we can tell encrypted from
# plaintext files regardless of the current ``file_encryption_enabled`` value.
_ENC_PREFIX = b"CAPOS-ENC1:"


# --------------------------------------------------------------------- helpers
def get_importer(importer_type: str) -> BaseTransactionImporter:
    cls = IMPORTER_REGISTRY.get(importer_type)
    if cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown importer '{importer_type}'")
    return cls()


def _sanitize_filename(filename: str) -> str:
    # Strip any directory components (defends against path traversal).
    base = Path(filename or "upload.csv").name
    safe = _FILENAME_SAFE.sub("_", base).strip("._") or "upload.csv"
    return safe[:200]


def _user_upload_dir(user_id: uuid.UUID) -> Path:
    root = Path(settings.upload_dir) / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_bytes(path: Path, content: bytes) -> None:
    if settings.file_encryption_enabled:
        # Encrypt the base64 of the raw bytes so arbitrary binary survives the
        # str-based Fernet helpers intact.
        b64 = base64.b64encode(content).decode("ascii")
        token = encrypt_str(b64)
        if token is None:  # pragma: no cover - encrypt_str only None on None input
            raise RuntimeError("Encryption failed for upload.")
        path.write_bytes(_ENC_PREFIX + token.encode("ascii"))
    else:
        path.write_bytes(content)


def _read_stored_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if data.startswith(_ENC_PREFIX):
        token = data[len(_ENC_PREFIX):].decode("ascii")
        b64 = decrypt_str(token)
        if b64 is None:
            raise HTTPException(status_code=500, detail="Could not decrypt stored file.")
        return base64.b64decode(b64)
    return data


def _kind_for(direction: str) -> str:
    return "income" if direction == "credit" else "expense"


# ----------------------------------------------------------------- save upload
def save_upload(
    db: Session,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    filename: str,
    content: bytes,
    importer_type: str,
) -> ImportBatch:
    """Validate, store (optionally encrypted) and register an uploaded file."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
        )
    if importer_type not in IMPORTER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown importer '{importer_type}'")

    # Account must exist and belong to the user.
    account = db.get(Account, account_id)
    if account is None or account.user_id != user_id:
        raise HTTPException(status_code=404, detail="Account not found")

    safe_name = _sanitize_filename(filename)
    checksum = hashlib.sha256(content).hexdigest()

    batch_id = uuid.uuid4()
    stored_name = f"{batch_id}_{safe_name}"
    dest = _user_upload_dir(user_id) / stored_name
    _write_bytes(dest, content)

    batch = ImportBatch(
        id=batch_id,
        user_id=user_id,
        account_id=account_id,
        original_filename=safe_name,
        storage_path=str(dest),
        file_checksum=checksum,
        importer_type=importer_type,
        status="uploaded",
    )
    db.add(batch)
    db.flush()
    return batch


# --------------------------------------------------------------------- parsing
def _load_and_parse(
    batch: ImportBatch, column_map: dict | None
) -> tuple[list[ParsedRow], list[str], list[tuple[int, str, dict]]]:
    """Read the stored file and parse it into ``ParsedRow`` objects.

    Returns (parsed_rows, columns, rejected) where ``rejected`` is a list of
    (row_number, reason, raw) tuples for rows that failed validation.
    """
    if not batch.storage_path:
        raise HTTPException(status_code=409, detail="No stored file for this batch.")
    path = Path(batch.storage_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Stored file is no longer available.")

    content = _read_stored_bytes(path)
    importer = get_importer(batch.importer_type)

    try:
        columns = importer.columns(content)
    except ImporterError:
        columns = []

    if importer.requires_column_map and not column_map:
        # Cannot parse yet — surface available columns for the mapping step.
        return [], columns, []

    try:
        parsed = importer.parse(content, column_map=column_map)
    except ImporterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    valid: list[ParsedRow] = []
    rejected: list[tuple[int, str, dict]] = []
    for idx, row in enumerate(parsed, start=1):
        reason = _validate_row(row)
        if reason:
            rejected.append((idx, reason, row.raw))
        else:
            valid.append(row)
    return valid, columns, rejected


def _validate_row(row: ParsedRow) -> str | None:
    if row.booking_date is None:
        return "Missing or unparseable date"
    if row.amount is None or D(row.amount) <= 0:
        return "Missing or non-positive amount"
    if row.direction not in ("credit", "debit"):
        return f"Invalid direction '{row.direction}'"
    if not row.currency or len(row.currency) != 3:
        return f"Invalid currency '{row.currency}'"
    return None


def _fingerprint_for(account: Account, row: ParsedRow) -> str:
    return build_fingerprint(
        account_id=str(account.id),
        booking_date=row.booking_date,
        amount=D(row.amount),
        currency=account.currency,
        description=row.description,
        value_date=row.value_date,
        external_id=row.external_id,
    )


def _existing_fingerprints(
    db: Session, account_id: uuid.UUID, fingerprints: set[str]
) -> set[str]:
    if not fingerprints:
        return set()
    stmt = select(Transaction.fingerprint).where(
        Transaction.account_id == account_id,
        Transaction.fingerprint.in_(fingerprints),
    )
    return set(db.scalars(stmt).all())


# --------------------------------------------------------------------- preview
def preview(db: Session, batch: ImportBatch, column_map: dict | None) -> dict:
    """Parse the file and report new/duplicate/rejected rows without writing."""
    account = db.get(Account, batch.account_id)
    if account is None or account.user_id != batch.user_id:
        raise HTTPException(status_code=404, detail="Account not found")

    rows, columns, rejected = _load_and_parse(batch, column_map)

    fingerprints = [_fingerprint_for(account, r) for r in rows]
    existing = _existing_fingerprints(db, account.id, set(fingerprints))

    rules = load_rules(db, batch.user_id)

    # Detect duplicates *within* the file too (same fingerprint twice).
    seen_in_file: set[str] = set()
    preview_rows: list[dict] = []
    duplicate_count = 0

    for row, fp in zip(rows, fingerprints, strict=True):
        is_dup = fp in existing or fp in seen_in_file
        if is_dup:
            duplicate_count += 1
        seen_in_file.add(fp)

        suggested_kind = _kind_for(row.direction)
        transient = _to_transient_txn(account, row, fp)
        matched = apply_rules(transient, rules)
        if matched:
            suggested_kind = transient.kind

        if len(preview_rows) < _PREVIEW_LIMIT:
            preview_rows.append(
                {
                    "booking_date": row.booking_date,
                    "value_date": row.value_date,
                    "description": row.description,
                    "original_description": row.original_description,
                    "amount": D(row.amount),
                    "direction": row.direction,
                    "currency": account.currency,
                    "merchant": transient.merchant,
                    "external_id": row.external_id,
                    "fingerprint": fp,
                    "is_duplicate": is_dup,
                    "suggested_category_id": transient.category_id,
                    "suggested_kind": suggested_kind,
                }
            )

    rejected_out = [
        {"row_number": rn, "reason": reason, "raw": raw}
        for rn, reason, raw in rejected
    ]

    return {
        "batch_id": batch.id,
        "total": len(rows),
        "duplicate_count": duplicate_count,
        "new_count": len(rows) - duplicate_count,
        "rejected_count": len(rejected),
        "columns": columns,
        "rows": preview_rows,
        "rejected": rejected_out,
    }


def _to_transient_txn(account: Account, row: ParsedRow, fingerprint: str) -> Transaction:
    """Build an unpersisted Transaction for rule evaluation / insertion."""
    return Transaction(
        user_id=account.user_id,
        account_id=account.id,
        booking_date=row.booking_date,
        value_date=row.value_date,
        description=row.description,
        original_description=row.original_description,
        merchant=row.merchant,
        amount=D(row.amount),
        currency=account.currency,
        direction=row.direction,
        kind=_kind_for(row.direction),
        status="booked",
        source="import",
        fingerprint=fingerprint,
        fingerprint_version=FINGERPRINT_VERSION,
        external_transaction_id=row.external_id,
        raw_data=row.raw or None,
    )


# ---------------------------------------------------------------------- commit
def commit_import(db: Session, batch: ImportBatch, column_map: dict | None) -> ImportBatch:
    """Insert non-duplicate rows as Transactions inside a single transaction."""
    if batch.status in ("completed", "partially_completed", "rolled_back"):
        raise HTTPException(
            status_code=409, detail=f"Batch already {batch.status}; cannot re-commit."
        )

    account = db.get(Account, batch.account_id)
    if account is None or account.user_id != batch.user_id:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        rows, _columns, rejected = _load_and_parse(batch, column_map)
    except HTTPException:
        batch.status = "failed"
        db.commit()
        raise

    rules = load_rules(db, batch.user_id)

    fingerprints = [_fingerprint_for(account, r) for r in rows]
    existing = _existing_fingerprints(db, account.id, set(fingerprints))

    imported = 0
    duplicates = 0
    seen: set[str] = set(existing)

    for row, fp in zip(rows, fingerprints, strict=True):
        if fp in seen:
            duplicates += 1
            continue
        seen.add(fp)

        txn = _to_transient_txn(account, row, fp)
        txn.import_batch_id = batch.id
        apply_rules(txn, rules)  # may override category / kind / transfer flags
        db.add(txn)
        imported += 1

    batch.imported_row_count = imported
    batch.duplicate_row_count = duplicates
    batch.rejected_row_count = len(rejected)
    batch.completed_at = datetime.now(UTC)

    if rejected and imported:
        batch.status = "partially_completed"
    elif imported == 0 and rejected:
        batch.status = "failed"
    else:
        batch.status = "completed"

    if rejected:
        batch.error_report = {
            "rejected": [
                {"row_number": rn, "reason": reason} for rn, reason, _raw in rejected
            ]
        }

    db.commit()
    db.refresh(batch)
    return batch


# -------------------------------------------------------------------- rollback
def rollback(db: Session, batch: ImportBatch) -> None:
    """Delete every Transaction created by this batch, then mark it rolled back."""
    if batch.status == "rolled_back":
        raise HTTPException(status_code=409, detail="Batch already rolled back.")

    txns = db.scalars(
        select(Transaction).where(
            Transaction.import_batch_id == batch.id,
            Transaction.user_id == batch.user_id,
        )
    ).all()
    for txn in txns:
        db.delete(txn)

    batch.status = "rolled_back"
    batch.imported_row_count = 0
    batch.completed_at = datetime.now(UTC)
    db.commit()
