"""Transactions: CRUD, filtering, bulk ops and transfer matching."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.calculations.transfers import TransferCandidate, propose_transfer_matches
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.providers.fx import ManualFxProvider
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message, Page
from app.schemas.transaction import (
    BulkCategorise,
    BulkResult,
    BulkReview,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
    TransferCandidateOut,
    TransferCandidateSide,
    TransferCreate,
    TransferLink,
    TransferLinkResult,
)
from app.services.audit import log_event
from app.services.transactions import (
    apply_rules,
    build_fingerprint,
    link_transfer,
    load_rules,
    signed_delta,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=Page[TransactionOut])
def list_transactions(
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    kind: str | None = None,
    status: str | None = None,
    direction: str | None = None,
    is_transfer: bool | None = None,
    is_reviewed: bool | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[TransactionOut]:
    conditions = [Transaction.user_id == user.id]
    if account_id is not None:
        conditions.append(Transaction.account_id == account_id)
    if category_id is not None:
        conditions.append(Transaction.category_id == category_id)
    if kind is not None:
        conditions.append(Transaction.kind == kind)
    if status is not None:
        conditions.append(Transaction.status == status)
    if direction is not None:
        conditions.append(Transaction.direction == direction)
    if is_transfer is not None:
        conditions.append(Transaction.is_transfer.is_(is_transfer))
    if is_reviewed is not None:
        conditions.append(Transaction.is_reviewed.is_(is_reviewed))
    if search:
        pattern = f"%{search}%"
        conditions.append(
            or_(Transaction.description.ilike(pattern), Transaction.merchant.ilike(pattern))
        )
    if date_from is not None:
        conditions.append(Transaction.booking_date >= date_from)
    if date_to is not None:
        conditions.append(Transaction.booking_date <= date_to)

    total = db.scalar(select(func.count()).select_from(Transaction).where(*conditions)) or 0
    stmt = (
        select(Transaction)
        .where(*conditions)
        .order_by(Transaction.booking_date.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(db.scalars(stmt).all())
    return Page[TransactionOut](
        items=[TransactionOut.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Transaction:
    account = get_owned_or_404(db, Account, payload.account_id, user.id)
    fingerprint = build_fingerprint(
        account_id=str(account.id),
        booking_date=payload.booking_date,
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        value_date=payload.value_date,
        external_id=payload.external_transaction_id,
    )
    existing = db.scalar(
        select(Transaction).where(
            Transaction.account_id == account.id,
            Transaction.fingerprint == fingerprint,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Duplicate transaction for this account")

    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        booking_date=payload.booking_date,
        value_date=payload.value_date,
        description=payload.description,
        original_description=payload.original_description,
        merchant=payload.merchant,
        counterparty=payload.counterparty,
        amount=payload.amount,
        currency=payload.currency,
        direction=payload.direction,
        kind=payload.kind,
        status=payload.status,
        category_id=payload.category_id,
        notes=payload.notes,
        external_transaction_id=payload.external_transaction_id,
        is_reviewed=payload.is_reviewed,
        source="manual",
        fingerprint=fingerprint,
    )
    apply_rules(txn, load_rules(db, user.id))
    db.add(txn)
    db.flush()
    # Manual entries move the account balance live so spending flows into the
    # dashboard/deployable-capital figures.
    account.current_balance = D(account.current_balance) + signed_delta(txn.amount, txn.direction)
    account.balance_date = date.today()
    log_event(db, action="transaction.create", user_id=user.id, entity_type="transaction",
              entity_id=txn.id, request=request, after={"amount": str(txn.amount)})
    db.commit()
    db.refresh(txn)
    return txn


@router.get("/transfer-candidates", response_model=list[TransferCandidateOut])
def transfer_candidates(
    days: int = Query(default=3, ge=0, le=30),
    tolerance: float = Query(default=0.02, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TransferCandidateOut]:
    """Propose likely internal-transfer pairs from recent, unlinked transactions."""
    since = date.today() - timedelta(days=90)
    stmt = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.is_transfer.is_(False),
        Transaction.booking_date >= since,
    )
    txns = list(db.scalars(stmt).all())
    by_id = {str(t.id): t for t in txns}
    candidates = [
        TransferCandidate(
            id=str(t.id),
            account_id=str(t.account_id),
            booking_date=t.booking_date,
            amount=Decimal(str(t.amount)),
            currency=t.currency,
            direction=t.direction,
            description=t.description,
        )
        for t in txns
    ]
    convert = ManualFxProvider(db, user.id).converter(user.base_currency)
    matches = propose_transfer_matches(
        candidates, convert, max_days_apart=days, tolerance=Decimal(str(tolerance))
    )

    def side(txn: Transaction) -> TransferCandidateSide:
        return TransferCandidateSide(
            id=txn.id,
            account_id=txn.account_id,
            booking_date=txn.booking_date,
            amount=Decimal(str(txn.amount)),
            currency=txn.currency,
            direction=txn.direction,
            description=txn.description,
        )

    return [
        TransferCandidateOut(
            debit=side(by_id[m.debit_id]),
            credit=side(by_id[m.credit_id]),
            confidence=m.confidence,
            fx_implied=m.fx_implied,
        )
        for m in matches
    ]


@router.post("/bulk-categorise", response_model=BulkResult)
def bulk_categorise(
    payload: BulkCategorise,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BulkResult:
    if payload.category_id is not None:
        get_owned_or_404(db, Category, payload.category_id, user.id)
    txns = list(
        db.scalars(
            select(Transaction).where(
                Transaction.user_id == user.id, Transaction.id.in_(payload.ids)
            )
        ).all()
    )
    for txn in txns:
        txn.category_id = payload.category_id
        if payload.mark_reviewed:
            txn.is_reviewed = True
    log_event(db, action="transaction.bulk_categorise", user_id=user.id,
              entity_type="transaction", request=request, after={"count": len(txns)})
    db.commit()
    return BulkResult(updated=len(txns))


@router.post("/bulk-review", response_model=BulkResult)
def bulk_review(
    payload: BulkReview,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BulkResult:
    txns = list(
        db.scalars(
            select(Transaction).where(
                Transaction.user_id == user.id, Transaction.id.in_(payload.ids)
            )
        ).all()
    )
    for txn in txns:
        txn.is_reviewed = payload.is_reviewed
    log_event(db, action="transaction.bulk_review", user_id=user.id,
              entity_type="transaction", request=request, after={"count": len(txns)})
    db.commit()
    return BulkResult(updated=len(txns))


@router.post("/transfer", response_model=TransferLinkResult, status_code=201)
def create_transfer(
    payload: TransferCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransferLinkResult:
    """Record money moving between two of your own accounts as a linked pair
    (debit out of one, credit into the other) and adjust both balances."""
    from_acc = get_owned_or_404(db, Account, payload.from_account_id, user.id)
    to_acc = get_owned_or_404(db, Account, payload.to_account_id, user.id)
    if from_acc.id == to_acc.id:
        raise HTTPException(status_code=400, detail="Choose two different accounts")
    to_amount = payload.to_amount if payload.to_amount is not None else payload.amount
    desc = payload.description or f"Transfer: {from_acc.name} to {to_acc.name}"

    debit_fp = build_fingerprint(
        account_id=str(from_acc.id), booking_date=payload.booking_date,
        amount=payload.amount, currency=from_acc.currency, description=desc,
        external_id="transfer-out",
    )
    credit_fp = build_fingerprint(
        account_id=str(to_acc.id), booking_date=payload.booking_date,
        amount=to_amount, currency=to_acc.currency, description=desc,
        external_id="transfer-in",
    )
    debit = Transaction(
        user_id=user.id, account_id=from_acc.id, booking_date=payload.booking_date,
        description=desc, amount=payload.amount, currency=from_acc.currency,
        direction="debit", kind="internal_transfer", status="booked", is_transfer=True,
        is_reviewed=True, source="manual", category_id=payload.category_id, fingerprint=debit_fp,
    )
    credit = Transaction(
        user_id=user.id, account_id=to_acc.id, booking_date=payload.booking_date,
        description=desc, amount=to_amount, currency=to_acc.currency,
        direction="credit", kind="internal_transfer", status="booked", is_transfer=True,
        is_reviewed=True, source="manual", category_id=payload.category_id, fingerprint=credit_fp,
    )
    db.add(debit)
    db.add(credit)
    db.flush()
    group_id = link_transfer(db, debit, credit)
    from_acc.current_balance = D(from_acc.current_balance) - D(payload.amount)
    to_acc.current_balance = D(to_acc.current_balance) + D(to_amount)
    from_acc.balance_date = date.today()
    to_acc.balance_date = date.today()
    log_event(db, action="transaction.create_transfer", user_id=user.id,
              entity_type="transaction", entity_id=group_id, request=request)
    db.commit()
    return TransferLinkResult(group_id=group_id)


@router.post("/transfers", response_model=TransferLinkResult)
def link_transfer_pair(
    payload: TransferLink,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransferLinkResult:
    debit = get_owned_or_404(db, Transaction, payload.debit_id, user.id)
    credit = get_owned_or_404(db, Transaction, payload.credit_id, user.id)
    group_id = link_transfer(db, debit, credit)
    log_event(db, action="transaction.link_transfer", user_id=user.id,
              entity_type="transaction", entity_id=group_id, request=request)
    db.commit()
    return TransferLinkResult(group_id=group_id)


@router.delete("/transfers/{group_id}", response_model=Message)
def unlink_transfer(
    group_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    txns = list(
        db.scalars(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.transfer_group_id == group_id,
            )
        ).all()
    )
    if not txns:
        raise HTTPException(status_code=404, detail="Transfer group not found")
    for txn in txns:
        txn.is_transfer = False
        txn.transfer_group_id = None
        txn.linked_account_id = None
        txn.kind = "income" if txn.direction == "credit" else "expense"
    log_event(db, action="transaction.unlink_transfer", user_id=user.id,
              entity_type="transaction", entity_id=group_id, request=request)
    db.commit()
    return Message(detail="Transfer unlinked")


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Transaction:
    return get_owned_or_404(db, Transaction, transaction_id, user.id)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Transaction:
    txn = get_owned_or_404(db, Transaction, transaction_id, user.id)
    is_manual = txn.source == "manual"
    old_account_id = txn.account_id
    old_delta = signed_delta(txn.amount, txn.direction)

    data = payload.model_dump(exclude_unset=True)
    if data.get("account_id") and data["account_id"] != old_account_id:
        get_owned_or_404(db, Account, data["account_id"], user.id)  # validate ownership
    for key, value in data.items():
        setattr(txn, key, value)

    if is_manual:
        new_delta = signed_delta(txn.amount, txn.direction)
        if txn.account_id == old_account_id:
            acc = db.get(Account, old_account_id)
            if acc is not None:
                acc.current_balance = D(acc.current_balance) - old_delta + new_delta
        else:
            old_acc = db.get(Account, old_account_id)
            new_acc = db.get(Account, txn.account_id)
            if old_acc is not None:
                old_acc.current_balance = D(old_acc.current_balance) - old_delta
            if new_acc is not None:
                new_acc.current_balance = D(new_acc.current_balance) + new_delta

    log_event(db, action="transaction.update", user_id=user.id, entity_type="transaction",
              entity_id=txn.id, request=request)
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/{transaction_id}", response_model=Message)
def delete_transaction(
    transaction_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    txn = get_owned_or_404(db, Transaction, transaction_id, user.id)
    if txn.source == "manual":
        acc = db.get(Account, txn.account_id)
        if acc is not None:
            acc.current_balance = D(acc.current_balance) - signed_delta(txn.amount, txn.direction)
    db.delete(txn)
    log_event(db, action="transaction.delete", user_id=user.id, entity_type="transaction",
              entity_id=transaction_id, request=request)
    db.commit()
    return Message(detail="Transaction deleted")
