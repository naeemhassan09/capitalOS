"""Enable Banking connections: authorize, map accounts, sync, disconnect.

Everything activates via configuration (ENABLE_BANKING_APP_ID + a readable
private key file). When unconfigured, read endpoints still work (empty lists)
but any action returns a clear 400.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.security import decrypt_str, encrypt_str
from app.models.account import Account
from app.models.bank_connection import BankAccountLink, BankConnection
from app.models.user import User
from app.providers.bankdata.enable_banking import (
    EnableBankingError,
    derive_display_name,
    derive_identifier_masked,
)
from app.repositories.base import get_owned_or_404
from app.schemas.bank_connection import (
    AspspOut,
    BankConnectionOut,
    BankStatusOut,
    BankSyncResultOut,
    CompleteRequest,
    CompleteResponse,
    ConnectRequest,
    ConnectResponse,
    CreateLinksRequest,
    DiscoveredAccountOut,
)
from app.schemas.common import Message
from app.services.audit import log_event
from app.services.bank_sync import make_client, sync_connection

router = APIRouter(prefix="/bank-connections", tags=["bank-connections"])

NOT_CONFIGURED_DETAIL = "Enable Banking is not configured"


def _require_configured() -> None:
    if not settings.enable_banking_configured:
        raise HTTPException(status_code=400, detail=NOT_CONFIGURED_DETAIL)


def _provider_http_error(exc: EnableBankingError) -> HTTPException:
    """Map provider failures: upstream 4xx → 400, everything else → 502."""
    if exc.status is not None and 400 <= exc.status < 500:
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


def _parse_dt(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _discovered_accounts(payload: dict, fallback_name: str) -> list[DiscoveredAccountOut]:
    """Extract discovered accounts defensively (cards may have no IBAN)."""
    candidates = payload.get("accounts") or []
    if not isinstance(candidates, list):
        return []
    # Some session-detail responses carry uids in `accounts` and the details
    # in `accounts_data` — prefer whichever list holds dicts.
    accounts_data = payload.get("accounts_data")
    if candidates and not isinstance(candidates[0], dict) and isinstance(accounts_data, list):
        candidates = accounts_data
    out: list[DiscoveredAccountOut] = []
    for item in candidates:
        if isinstance(item, dict):
            uid = str(item.get("uid") or item.get("identification_hash") or "").strip()
            if not uid:
                continue
            out.append(
                DiscoveredAccountOut(
                    uid=uid,
                    name=derive_display_name(item, fallback=fallback_name),
                    identifier_masked=derive_identifier_masked(item),
                    currency=(item.get("currency") or None),
                )
            )
        elif isinstance(item, str) and item.strip():
            out.append(
                DiscoveredAccountOut(
                    uid=item.strip(), name=fallback_name, identifier_masked="", currency=None
                )
            )
    return out


# --------------------------------------------------------------------- reads
@router.get("/status", response_model=BankStatusOut)
def bank_status(user: User = Depends(get_current_user)) -> BankStatusOut:
    return BankStatusOut(configured=settings.enable_banking_configured)


@router.get("", response_model=list[BankConnectionOut])
def list_connections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BankConnection]:
    stmt = (
        select(BankConnection)
        .where(BankConnection.user_id == user.id)
        .options(selectinload(BankConnection.links))
        .order_by(BankConnection.created_at.desc())
    )
    return list(db.scalars(stmt).all())


@router.get("/aspsps", response_model=list[AspspOut])
def list_aspsps(
    country: str = "IE",
    user: User = Depends(get_current_user),
) -> list[AspspOut]:
    _require_configured()
    try:
        aspsps = make_client().list_aspsps(country)
    except EnableBankingError as exc:
        raise _provider_http_error(exc) from exc
    return [
        AspspOut(name=a.get("name", ""), country=a.get("country", country.upper()))
        for a in aspsps
        if a.get("name")
    ]


# ------------------------------------------------------------ authorization
@router.post("/connect", response_model=ConnectResponse)
def connect_bank(
    payload: ConnectRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConnectResponse:
    _require_configured()
    state = str(uuid.uuid4())
    connection = BankConnection(
        user_id=user.id,
        provider="enable_banking",
        aspsp_name=payload.aspsp_name,
        aspsp_country=payload.aspsp_country.upper(),
        state=state,
        status="pending",
    )
    db.add(connection)
    db.flush()
    try:
        url = make_client().start_auth(
            aspsp_name=payload.aspsp_name,
            aspsp_country=payload.aspsp_country,
            state=state,
            redirect_url=f"{settings.app_url.rstrip('/')}/bank-callback",
        )
    except EnableBankingError as exc:
        db.rollback()
        raise _provider_http_error(exc) from exc
    log_event(db, action="bank_connection.connect", user_id=user.id,
              entity_type="bank_connection", entity_id=connection.id, request=request,
              after={"aspsp": payload.aspsp_name, "country": payload.aspsp_country.upper()})
    db.commit()
    return ConnectResponse(url=url, connection_id=connection.id)


@router.post("/complete", response_model=CompleteResponse)
def complete_auth(
    payload: CompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompleteResponse:
    _require_configured()
    connection = db.scalar(
        select(BankConnection).where(
            BankConnection.user_id == user.id,
            BankConnection.state == payload.state,
            BankConnection.status == "pending",
        )
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="No pending bank connection for this state")
    try:
        session = make_client().create_session(payload.code)
    except EnableBankingError as exc:
        raise _provider_http_error(exc) from exc

    session_id = session.get("session_id")
    if not session_id:
        raise HTTPException(status_code=502, detail="Provider returned no session id")
    connection.encrypted_session_id = encrypt_str(str(session_id))
    connection.valid_until = _parse_dt((session.get("access") or {}).get("valid_until"))
    connection.status = "active"

    log_event(db, action="bank_connection.complete", user_id=user.id,
              entity_type="bank_connection", entity_id=connection.id, request=request,
              after={"aspsp": connection.aspsp_name, "status": "active"})
    db.commit()
    return CompleteResponse(
        connection_id=connection.id,
        aspsp_name=connection.aspsp_name,
        accounts=_discovered_accounts(session, connection.aspsp_name),
    )


@router.get("/{connection_id}/accounts", response_model=list[DiscoveredAccountOut])
def discover_accounts(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DiscoveredAccountOut]:
    """Re-discover the authorized bank accounts of an active connection."""
    _require_configured()
    connection = get_owned_or_404(db, BankConnection, connection_id, user.id)
    session_id = decrypt_str(connection.encrypted_session_id)
    if connection.status != "active" or not session_id:
        raise HTTPException(status_code=400, detail="Connection is not active")
    try:
        session = make_client().get_session(session_id)
    except EnableBankingError as exc:
        raise _provider_http_error(exc) from exc
    return _discovered_accounts(session, connection.aspsp_name)


# ------------------------------------------------------------------ mapping
@router.post("/links", response_model=BankConnectionOut)
def create_links(
    payload: CreateLinksRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BankConnection:
    connection = get_owned_or_404(db, BankConnection, payload.connection_id, user.id)
    created = 0
    for mapping in payload.mappings:
        account = get_owned_or_404(db, Account, mapping.account_id, user.id)
        already = any(link.account_id == account.id for link in connection.links)
        if already:
            continue
        connection.links.append(
            BankAccountLink(
                account_id=account.id,
                encrypted_external_uid=encrypt_str(mapping.external_uid),
                display_name=mapping.display_name or account.name,
                identifier_masked=mapping.identifier_masked,
                currency=(mapping.currency or account.currency or "").upper()[:3] or None,
                enabled=True,
            )
        )
        created += 1
    log_event(db, action="bank_connection.links_create", user_id=user.id,
              entity_type="bank_connection", entity_id=connection.id, request=request,
              after={"links_created": created})
    db.commit()
    db.refresh(connection)
    return connection


# --------------------------------------------------------------------- sync
@router.post("/{connection_id}/sync", response_model=BankSyncResultOut)
def sync_now(
    connection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BankSyncResultOut:
    _require_configured()
    connection = get_owned_or_404(db, BankConnection, connection_id, user.id)
    try:
        result = sync_connection(db, user, connection)
    except EnableBankingError as exc:
        if exc.is_auth_error:
            raise HTTPException(
                status_code=400,
                detail="Bank authorisation has expired — reconnect the bank.",
            ) from exc
        raise _provider_http_error(exc) from exc
    log_event(db, action="bank_connection.sync", user_id=user.id,
              entity_type="bank_connection", entity_id=connection.id, request=request,
              after={k: v for k, v in result.items() if k != "errors"})
    db.commit()
    return BankSyncResultOut(**result)


@router.delete("/{connection_id}", response_model=Message)
def delete_connection(
    connection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    connection = get_owned_or_404(db, BankConnection, connection_id, user.id)
    db.delete(connection)  # links cascade
    log_event(db, action="bank_connection.delete", user_id=user.id,
              entity_type="bank_connection", entity_id=connection_id, request=request,
              after={"aspsp": connection.aspsp_name})
    db.commit()
    return Message(detail="Bank connection removed")
