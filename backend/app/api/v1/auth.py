"""Authentication routes: first-run setup, login, logout, session management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, generate_csrf_token
from app.core.db import get_db
from app.core.deps import get_client_ip, get_current_user
from app.core.security import (
    hash_password,
    sign_session,
    verify_password,
)
from app.models.user import User, UserSession
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    PinLoginRequest,
    SessionOut,
    SetPinRequest,
    SetupRequest,
    SetupStatus,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth as auth_service
from app.services.audit import log_event

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, session: UserSession) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sign_session(str(session.id)),
        max_age=settings.session_max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        max_age=settings.session_max_age,
        httponly=False,  # readable by the SPA for double-submit
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.get("/setup-status", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db)) -> SetupStatus:
    return SetupStatus(
        initialized=auth_service.is_initialized(db),
        pin_enabled=auth_service.pin_enabled(db),
    )


@router.post("/pin/login", response_model=UserOut)
def pin_login(
    payload: PinLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    ip = get_client_ip(request)
    user = auth_service.authenticate_pin(db, pin=payload.pin, ip=ip)
    session = auth_service.create_session(
        db, user=user, ip=ip, user_agent=request.headers.get("user-agent")
    )
    log_event(db, action="auth.pin_login", user_id=user.id, entity_type="user",
              entity_id=user.id, request=request)
    db.commit()
    _set_auth_cookies(response, session)
    return user


@router.post("/pin", response_model=Message)
def set_pin(
    payload: SetPinRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    auth_service.set_pin(db, user=user, current_password=payload.current_password, pin=payload.pin)
    log_event(db, action="auth.set_pin", user_id=user.id, request=request)
    db.commit()
    return Message(detail="PIN set")


@router.delete("/pin", response_model=Message)
def delete_pin(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    auth_service.remove_pin(db, user=user)
    log_event(db, action="auth.remove_pin", user_id=user.id, request=request)
    db.commit()
    return Message(detail="PIN removed")


@router.post("/setup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def setup(
    payload: SetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    ip = get_client_ip(request)
    user = auth_service.create_owner(
        db,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        base_currency=payload.base_currency,
        timezone=payload.timezone,
    )
    session = auth_service.create_session(
        db, user=user, ip=ip, user_agent=request.headers.get("user-agent")
    )
    log_event(db, action="auth.setup", user_id=user.id, entity_type="user",
              entity_id=user.id, request=request)
    db.commit()
    _set_auth_cookies(response, session)
    return user


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    ip = get_client_ip(request)
    user = auth_service.authenticate(db, email=payload.email, password=payload.password, ip=ip)
    session = auth_service.create_session(
        db, user=user, ip=ip, user_agent=request.headers.get("user-agent")
    )
    log_event(db, action="auth.login", user_id=user.id, entity_type="user",
              entity_id=user.id, request=request)
    db.commit()
    _set_auth_cookies(response, session)
    return user


@router.post("/logout", response_model=Message)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    session: UserSession | None = getattr(request.state, "session", None)
    if session is not None:
        auth_service.revoke_session(db, session.id)
        log_event(db, action="auth.logout", user_id=user.id, request=request)
        db.commit()
    _clear_auth_cookies(response)
    return Message(detail="Logged out")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", response_model=Message)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect."
        )
    user.password_hash = hash_password(payload.new_password)
    log_event(db, action="auth.change_password", user_id=user.id, request=request)
    db.commit()
    return Message(detail="Password changed")


@router.get("/sessions", response_model=list[SessionOut])
def sessions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SessionOut]:
    current: UserSession | None = getattr(request.state, "session", None)
    current_id = current.id if current else None
    out: list[SessionOut] = []
    for s in auth_service.list_active_sessions(db, user.id):
        item = SessionOut.model_validate(s)
        item.current = s.id == current_id
        out.append(item)
    return out


@router.delete("/sessions/{session_id}", response_model=Message)
def revoke(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    import uuid

    try:
        sid = uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    sess = db.get(UserSession, sid)
    if sess is None or sess.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    auth_service.revoke_session(db, sid)
    log_event(db, action="auth.revoke_session", user_id=user.id, entity_id=sid, request=request)
    db.commit()
    return Message(detail="Session revoked")
