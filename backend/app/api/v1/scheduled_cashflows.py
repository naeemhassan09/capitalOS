"""Scheduled cashflows CRUD."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from dateutil.rrule import rrulestr
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.account import Account
from app.models.scheduled_cashflow import ScheduledCashflow
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.scheduled_cashflow import (
    MarkPaidRequest,
    ScheduledCashflowCreate,
    ScheduledCashflowOut,
    ScheduledCashflowUpdate,
)
from app.schemas.transaction import TransactionOut
from app.services.audit import log_event
from app.services.transactions import build_fingerprint, signed_delta


def _next_due_after(cf: ScheduledCashflow) -> date | None:
    """Next occurrence strictly after the current next_due_date, or None."""
    if not cf.recurrence_rule:
        return None
    rule = rrulestr(
        cf.recurrence_rule,
        dtstart=datetime.combine(cf.first_due_date, datetime.min.time()),
    )
    nxt = rule.after(datetime.combine(cf.next_due_date, datetime.min.time()), inc=False)
    if nxt is None:
        return None
    d = nxt.date()
    if cf.end_date and d > cf.end_date:
        return None
    return d

router = APIRouter(prefix="/scheduled-cashflows", tags=["scheduled-cashflows"])


@router.get("", response_model=list[ScheduledCashflowOut])
def list_cashflows(
    status: str | None = None,
    direction: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScheduledCashflow]:
    stmt = select(ScheduledCashflow).where(ScheduledCashflow.user_id == user.id)
    if status is not None:
        stmt = stmt.where(ScheduledCashflow.status == status)
    if direction is not None:
        stmt = stmt.where(ScheduledCashflow.direction == direction)
    stmt = stmt.order_by(ScheduledCashflow.next_due_date, ScheduledCashflow.priority)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ScheduledCashflowOut, status_code=201)
def create_cashflow(
    payload: ScheduledCashflowCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledCashflow:
    data = payload.model_dump()
    if data.get("next_due_date") is None:
        data["next_due_date"] = data["first_due_date"]
    cashflow = ScheduledCashflow(user_id=user.id, **data)
    db.add(cashflow)
    db.flush()
    log_event(db, action="scheduled_cashflow.create", user_id=user.id,
              entity_type="scheduled_cashflow", entity_id=cashflow.id, request=request,
              after={"name": cashflow.name})
    db.commit()
    db.refresh(cashflow)
    return cashflow


@router.post("/{cashflow_id}/mark-paid", response_model=TransactionOut, status_code=201)
def mark_paid(
    cashflow_id: uuid.UUID,
    payload: MarkPaidRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Transaction:
    """Record this due occurrence as a real transaction (adjusting the account
    balance), then advance a recurring schedule or mark a one-off as paid."""
    cf = get_owned_or_404(db, ScheduledCashflow, cashflow_id, user.id)
    account_id = payload.account_id or cf.account_id
    if account_id is None:
        raise HTTPException(
            status_code=400, detail="No account set on this cashflow — pass account_id."
        )
    account = get_owned_or_404(db, Account, account_id, user.id)
    booking = payload.booking_date or cf.next_due_date

    direction = "debit" if cf.direction == "outflow" else "credit"
    kind = "expense" if cf.direction == "outflow" else "income"
    fp = build_fingerprint(
        account_id=str(account.id), booking_date=booking, amount=cf.amount,
        currency=account.currency, description=cf.name,
        external_id=f"schedpaid-{cf.id}-{booking.isoformat()}",
    )
    txn = Transaction(
        user_id=user.id, account_id=account.id, booking_date=booking, description=cf.name,
        amount=cf.amount, currency=account.currency, direction=direction, kind=kind,
        status="booked", category_id=cf.category_id, is_reviewed=True, source="manual",
        fingerprint=fp,
    )
    db.add(txn)
    db.flush()
    account.current_balance = D(account.current_balance) + signed_delta(cf.amount, direction)
    account.balance_date = date.today()

    # Advance the schedule so this occurrence isn't counted again.
    next_due = _next_due_after(cf)
    if next_due is not None:
        cf.next_due_date = next_due
        cf.status = "planned"
    else:
        cf.status = "paid"

    log_event(db, action="scheduled_cashflow.mark_paid", user_id=user.id,
              entity_type="scheduled_cashflow", entity_id=cf.id, request=request,
              after={"transaction_id": str(txn.id)})
    db.commit()
    db.refresh(txn)
    return txn


@router.get("/{cashflow_id}", response_model=ScheduledCashflowOut)
def get_cashflow(
    cashflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledCashflow:
    return get_owned_or_404(db, ScheduledCashflow, cashflow_id, user.id)


@router.patch("/{cashflow_id}", response_model=ScheduledCashflowOut)
def update_cashflow(
    cashflow_id: uuid.UUID,
    payload: ScheduledCashflowUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledCashflow:
    cashflow = get_owned_or_404(db, ScheduledCashflow, cashflow_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cashflow, key, value)
    log_event(db, action="scheduled_cashflow.update", user_id=user.id,
              entity_type="scheduled_cashflow", entity_id=cashflow.id, request=request)
    db.commit()
    db.refresh(cashflow)
    return cashflow


@router.delete("/{cashflow_id}", response_model=Message)
def delete_cashflow(
    cashflow_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    cashflow = get_owned_or_404(db, ScheduledCashflow, cashflow_id, user.id)
    db.delete(cashflow)
    log_event(db, action="scheduled_cashflow.delete", user_id=user.id,
              entity_type="scheduled_cashflow", entity_id=cashflow_id, request=request)
    db.commit()
    return Message(detail="Scheduled cashflow deleted")
