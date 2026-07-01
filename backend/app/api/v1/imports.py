"""CSV import API: upload, preview, commit, rollback and listing."""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.importers import IMPORTER_REGISTRY
from app.importers.manual_template import ManualTemplateImporter
from app.models.import_batch import ImportBatch
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.imports import (
    ColumnMapRequest,
    CommitRequest,
    ImportBatchOut,
    ImporterInfo,
    PreviewResponse,
)
from app.services import imports as imports_service
from app.services.audit import log_event

router = APIRouter(prefix="/imports", tags=["imports"])

# Content types browsers / OSes commonly attach to .csv files. We do not trust
# MIME alone (checked alongside the .csv extension).
_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
    "",
}

# Cells starting with these are prefixed with a quote to defuse CSV/formula
# injection when the exported template is opened in a spreadsheet app.
_INJECTION_PREFIXES = ("=", "+", "-", "@")


def _sanitize_csv_cell(cell: str) -> str:
    if cell and cell[0] in _INJECTION_PREFIXES:
        return "'" + cell
    return cell


@router.get("", response_model=list[ImportBatchOut])
def list_batches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ImportBatch]:
    stmt = (
        select(ImportBatch)
        .where(ImportBatch.user_id == user.id)
        .order_by(ImportBatch.created_at.desc())
    )
    return list(db.scalars(stmt).all())


@router.get("/importers", response_model=list[ImporterInfo])
def list_importers() -> list[ImporterInfo]:
    return [
        ImporterInfo(
            importer_type=cls.importer_type,
            display_name=cls.display_name,
            requires_column_map=cls.requires_column_map,
        )
        for cls in IMPORTER_REGISTRY.values()
    ]


@router.get("/template")
def download_template() -> Response:
    """Return the manual-entry template as a downloadable CSV."""
    raw = ManualTemplateImporter.template_csv()
    # Defuse formula injection on a per-cell basis.
    safe_lines: list[str] = []
    for line in raw.splitlines():
        cells = [_sanitize_csv_cell(c) for c in line.split(",")]
        safe_lines.append(",".join(cells))
    body = "\r\n".join(safe_lines) + "\r\n"
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="capitalos_import_template.csv"'
        },
    )


@router.post("/upload", response_model=ImportBatchOut, status_code=201)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    account_id: uuid.UUID = Form(...),
    importer_type: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportBatch:
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")
    if (file.content_type or "") not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type '{file.content_type}'.",
        )
    if importer_type not in IMPORTER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown importer '{importer_type}'")

    content = await file.read()
    # Guard against streaming a file larger than allowed before touching disk.
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
        )

    batch = imports_service.save_upload(
        db,
        user_id=user.id,
        account_id=account_id,
        filename=filename,
        content=content,
        importer_type=importer_type,
    )
    log_event(
        db,
        action="import.upload",
        user_id=user.id,
        entity_type="import_batch",
        entity_id=batch.id,
        request=request,
        after={
            "filename": batch.original_filename,
            "importer_type": batch.importer_type,
            "checksum": batch.file_checksum,
        },
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/{batch_id}/preview", response_model=PreviewResponse)
def preview_batch(
    batch_id: uuid.UUID,
    payload: ColumnMapRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    batch = get_owned_or_404(db, ImportBatch, batch_id, user.id)
    column_map = payload.column_map if payload else None
    result = imports_service.preview(db, batch, column_map)
    if batch.status in ("uploaded", "validating", "preview_ready"):
        batch.status = "preview_ready"
        db.commit()
    return result


@router.post("/{batch_id}/commit", response_model=ImportBatchOut)
def commit_batch(
    batch_id: uuid.UUID,
    request: Request,
    payload: CommitRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportBatch:
    batch = get_owned_or_404(db, ImportBatch, batch_id, user.id)
    column_map = payload.column_map if payload else None
    batch = imports_service.commit_import(db, batch, column_map)
    log_event(
        db,
        action="import.commit",
        user_id=user.id,
        entity_type="import_batch",
        entity_id=batch.id,
        request=request,
        after={
            "status": batch.status,
            "imported": batch.imported_row_count,
            "duplicates": batch.duplicate_row_count,
            "rejected": batch.rejected_row_count,
        },
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/{batch_id}/rollback", response_model=Message)
def rollback_batch(
    batch_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    batch = get_owned_or_404(db, ImportBatch, batch_id, user.id)
    imports_service.rollback(db, batch)
    log_event(
        db,
        action="import.rollback",
        user_id=user.id,
        entity_type="import_batch",
        entity_id=batch.id,
        request=request,
        after={"status": batch.status},
    )
    db.commit()
    return Message(detail="Import rolled back")


@router.get("/{batch_id}", response_model=ImportBatchOut)
def get_batch(
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportBatch:
    return get_owned_or_404(db, ImportBatch, batch_id, user.id)
