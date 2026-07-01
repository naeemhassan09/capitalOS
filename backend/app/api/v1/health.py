"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    checks: dict[str, str] = {}
    healthy = True
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "error"
        healthy = False
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    checks["status"] = "ok" if healthy else "degraded"
    return checks
