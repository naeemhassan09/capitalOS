"""Authentication service: setup, login, sessions, rate limiting."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User, UserSession
from app.services.defaults import seed_defaults_for_user

# In-process login throttle (single-instance local deployment). Keyed by IP.
_attempts: dict[str, deque[float]] = defaultdict(deque)
# PINs are short, so throttle them harder than passwords.
_pin_attempts: dict[str, deque[float]] = defaultdict(deque)
PIN_MAX_ATTEMPTS = 5
PIN_WINDOW_SECONDS = 900  # 15 minutes


def _check_rate_limit(ip: str | None) -> None:
    if ip is None:
        return
    now = time.time()
    window = settings.login_window_seconds
    q = _attempts[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= settings.login_max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait and try again.",
        )


def _record_attempt(ip: str | None) -> None:
    if ip is not None:
        _attempts[ip].append(time.time())


def _clear_attempts(ip: str | None) -> None:
    if ip is not None and ip in _attempts:
        _attempts[ip].clear()


def is_initialized(db: Session) -> bool:
    return db.scalar(select(User.id).limit(1)) is not None


def pin_enabled(db: Session) -> bool:
    owner = db.scalar(select(User).where(User.is_owner.is_(True)))
    return bool(owner and owner.pin_hash)


def create_owner(db: Session, *, email: str, password: str, display_name: str,
                 base_currency: str, timezone: str) -> User:
    if is_initialized(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application is already initialised.",
        )
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        base_currency=base_currency.upper(),
        timezone=timezone,
        is_owner=True,
        is_active=True,
    )
    db.add(user)
    db.flush()
    seed_defaults_for_user(db, user.id, user.display_name)
    return user


def authenticate(db: Session, *, email: str, password: str, ip: str | None) -> User:
    _check_rate_limit(ip)
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash):
        _record_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled."
        )
    _clear_attempts(ip)
    user.last_login_at = datetime.now(UTC)
    return user


def _check_pin_rate_limit(ip: str | None) -> None:
    if ip is None:
        return
    now = time.time()
    q = _pin_attempts[ip]
    while q and now - q[0] > PIN_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= PIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many PIN attempts. Please wait 15 minutes or use your password.",
        )


def set_pin(db: Session, *, user: User, current_password: str, pin: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect."
        )
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="PIN must be 4-8 digits."
        )
    user.pin_hash = hash_password(pin)


def remove_pin(db: Session, *, user: User) -> None:
    user.pin_hash = None


def authenticate_pin(db: Session, *, pin: str, ip: str | None) -> User:
    _check_pin_rate_limit(ip)
    owner = db.scalar(select(User).where(User.is_owner.is_(True)))
    if owner is None or owner.pin_hash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="PIN sign-in is not set up."
        )
    if not owner.is_active or not verify_password(pin, owner.pin_hash):
        _pin_attempts[ip].append(time.time()) if ip else None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN.")
    if ip and ip in _pin_attempts:
        _pin_attempts[ip].clear()
    owner.last_login_at = datetime.now(UTC)
    return owner


def create_session(db: Session, *, user: User, ip: str | None, user_agent: str | None
                   ) -> UserSession:
    sess = UserSession(
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.session_max_age),
        ip_address=ip,
        user_agent=(user_agent or "")[:400] or None,
    )
    db.add(sess)
    db.flush()
    return sess


def revoke_session(db: Session, session_id: uuid.UUID) -> None:
    sess = db.get(UserSession, session_id)
    if sess and sess.revoked_at is None:
        sess.revoked_at = datetime.now(UTC)


def list_active_sessions(db: Session, user_id: uuid.UUID) -> list[UserSession]:
    now = datetime.now(UTC)
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_seen_at.desc())
    ).all()
    return [s for s in rows if s.expires_at >= now]
