"""Shared FastAPI dependencies (current user / session resolution)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import unsign_session
from app.models.user import User, UserSession


def get_client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _resolve_session(request: Request, db: Session) -> UserSession | None:
    signed = request.cookies.get(settings.session_cookie_name)
    if not signed:
        return None
    session_id = unsign_session(signed)
    if not session_id:
        return None
    sess = db.get(UserSession, session_id)
    if sess is None or sess.revoked_at is not None:
        return None
    expires_at = sess.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        return None
    return sess


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    sess = _resolve_session(request, db)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    # Touch last-seen (cheap; single row update).
    sess.last_seen_at = datetime.now(UTC)
    request.state.session = sess
    db.commit()
    return user


def owner_exists(db: Session) -> bool:
    return db.scalar(select(User).where(User.is_owner.is_(True)).limit(1)) is not None
