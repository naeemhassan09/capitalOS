"""Accounts CRUD, archive and manual balance adjustment."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.security import encrypt_str
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.account import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    BalanceAdjustment,
)
from app.schemas.common import Message
from app.services.audit import log_event
from app.services.transactions import build_fingerprint

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(
    country: str | None = None,
    account_type: str | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Account]:
    stmt = select(Account).where(Account.user_id == user.id)
    if country:
        stmt = stmt.where(Account.country == country)
    if account_type:
        stmt = stmt.where(Account.account_type == account_type)
    if not include_archived:
        stmt = stmt.where(Account.is_archived.is_(False))
    stmt = stmt.order_by(Account.country, Account.name)
    return list(db.scalars(stmt).all())


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    payload: AccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Account:
    data = payload.model_dump()
    iban = data.pop("iban", None)
    account = Account(user_id=user.id, **data)
    if iban:
        account.encrypted_iban = encrypt_str(iban)
    db.add(account)
    db.flush()
    log_event(db, action="account.create", user_id=user.id, entity_type="account",
              entity_id=account.id, request=request, after={"name": account.name})
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Account:
    return get_owned_or_404(db, Account, account_id, user.id)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Account:
    account = get_owned_or_404(db, Account, account_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    iban = data.pop("iban", None)
    if iban is not None:
        account.encrypted_iban = encrypt_str(iban) if iban else None
    for key, value in data.items():
        setattr(account, key, value)
    log_event(db, action="account.update", user_id=user.id, entity_type="account",
              entity_id=account.id, request=request)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", response_model=Message)
def archive_account(
    account_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    account = get_owned_or_404(db, Account, account_id, user.id)
    account.is_archived = True
    log_event(db, action="account.archive", user_id=user.id, entity_type="account",
              entity_id=account.id, request=request)
    db.commit()
    return Message(detail="Account archived")


@router.post("/{account_id}/adjust-balance", response_model=AccountOut)
def adjust_balance(
    account_id: uuid.UUID,
    payload: BalanceAdjustment,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Account:
    """Set an account to a new balance, recording an adjustment transaction."""
    account = get_owned_or_404(db, Account, account_id, user.id)
    old = account.current_balance
    delta = payload.new_balance - old
    as_of = payload.as_of or date.today()

    if delta != 0:
        direction = "credit" if delta > 0 else "debit"
        txn = Transaction(
            user_id=user.id,
            account_id=account.id,
            booking_date=as_of,
            description=payload.note or "Manual balance adjustment",
            amount=abs(delta),
            currency=account.currency,
            direction=direction,
            kind="adjustment",
            status="booked",
            source="manual",
            is_reviewed=True,
            fingerprint="",
        )
        txn.fingerprint = build_fingerprint(
            account_id=str(account.id),
            booking_date=as_of,
            amount=abs(delta),
            currency=account.currency,
            description=txn.description,
        )
        db.add(txn)

    account.current_balance = payload.new_balance
    account.balance_date = as_of
    log_event(db, action="account.adjust_balance", user_id=user.id, entity_type="account",
              entity_id=account.id, request=request,
              before={"balance": str(old)}, after={"balance": str(payload.new_balance)})
    db.commit()
    db.refresh(account)
    return account
