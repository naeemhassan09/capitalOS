"""Audit logging helper."""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import get_client_ip
from app.models.audit import AuditLog


def log_event(
    db: Session,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    request: Request | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        source_ip=get_client_ip(request) if request else None,
        user_agent=(request.headers.get("user-agent")[:400] if request else None),
        before=before,
        after=after,
    )
    db.add(entry)
    return entry
