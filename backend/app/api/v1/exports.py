"""Data-export endpoints: full JSON export and per-entity CSV downloads.

All CSV output is defended against spreadsheet formula injection: any cell whose
stringified value begins with one of ``= + - @ <TAB> <CR>`` is prefixed with a
single quote before writing. Every export is audit-logged.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.account import Account
from app.models.category import Category
from app.models.exchange_rate import ExchangeRate
from app.models.goal import SavingsGoal
from app.models.holding import Holding
from app.models.reserve import ReservePolicy
from app.models.rule import CategorisationRule
from app.models.scheduled_cashflow import ScheduledCashflow
from app.models.transaction import Transaction
from app.models.user import User
from app.services.audit import log_event

router = APIRouter(prefix="/exports", tags=["exports"])

# Leading characters that spreadsheet apps may interpret as a formula.
_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> str:
    """Stringify ``value`` and neutralise spreadsheet formula injection.

    If the stringified value begins with a dangerous prefix, a single quote is
    prepended so spreadsheet software treats it as literal text.
    """
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in _INJECTION_PREFIXES:
        return "'" + text
    return text


def _jsonable(value: Any) -> Any:
    """Recursively coerce ORM-derived values into JSON-serialisable forms,
    keeping money as strings so Decimal precision is never lost to float."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _row_to_dict(obj: Any) -> dict[str, Any]:
    """Serialise a mapped ORM instance's columns to a JSON-safe dict."""
    mapper = obj.__class__.__mapper__
    out: dict[str, Any] = {}
    for col in mapper.columns:
        out[col.key] = _jsonable(getattr(obj, col.key))
    return out


def _csv_response(header: list[str], rows: list[list[Any]], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([csv_safe(h) for h in header])
    for row in rows:
        writer.writerow([csv_safe(cell) for cell in row])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------- full JSON
@router.get("/full.json")
def export_full_json(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Complete JSON export of the user's data, streamed as an attachment."""
    uid = user.id

    def rows(model):
        stmt = select(model).where(model.user_id == uid)
        return [_row_to_dict(r) for r in db.scalars(stmt).all()]

    payload = {
        "meta": {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "base_currency": user.base_currency,
            "user_email": user.email,
            "schema": "capitalos.full_export.v1",
        },
        "accounts": rows(Account),
        "transactions": rows(Transaction),
        "categories": rows(Category),
        "rules": rows(CategorisationRule),
        "goals": rows(SavingsGoal),
        "reserves": rows(ReservePolicy),
        "holdings": rows(Holding),
        "scheduled_cashflows": rows(ScheduledCashflow),
        "exchange_rates": rows(ExchangeRate),
    }

    log_event(db, action="export.full_json", user_id=uid, request=request)
    db.commit()

    def stream():
        # Serialise in chunks so a very large export never buffers fully in RAM.
        yield "{"
        first = True
        for key, value in payload.items():
            prefix = "" if first else ","
            first = False
            yield f'{prefix}{json.dumps(key)}:{json.dumps(value)}'
        yield "}"

    return StreamingResponse(
        stream(),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="capitalos_export.json"'
        },
    )


# ------------------------------------------------------------------ CSV: txns
@router.get("/transactions.csv")
def export_transactions_csv(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    txns = db.scalars(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.booking_date.desc())
    ).all()
    header = [
        "id", "booking_date", "value_date", "description", "merchant",
        "counterparty", "amount", "currency", "base_currency_amount",
        "exchange_rate", "direction", "kind", "status", "account_id",
        "category_id", "is_transfer", "is_recurring", "is_reviewed", "source",
        "notes",
    ]
    rows = [
        [
            t.id, t.booking_date, t.value_date, t.description, t.merchant,
            t.counterparty, t.amount, t.currency, t.base_currency_amount,
            t.exchange_rate, t.direction, t.kind, t.status, t.account_id,
            t.category_id, t.is_transfer, t.is_recurring, t.is_reviewed,
            t.source, t.notes,
        ]
        for t in txns
    ]
    log_event(db, action="export.transactions_csv", user_id=user.id, request=request)
    db.commit()
    return _csv_response(header, rows, "capitalos_transactions.csv")


# -------------------------------------------------------------- CSV: accounts
@router.get("/accounts.csv")
def export_accounts_csv(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    accounts = db.scalars(
        select(Account).where(Account.user_id == user.id).order_by(Account.name)
    ).all()
    header = [
        "id", "name", "account_type", "account_subtype", "currency", "country",
        "institution_id", "masked_identifier", "opening_balance",
        "current_balance", "balance_date", "credit_limit",
        "include_in_net_worth", "include_in_liquid_assets",
        "is_protected_reserve", "is_archived",
    ]
    rows = [
        [
            a.id, a.name, a.account_type, a.account_subtype, a.currency,
            a.country, a.institution_id, a.masked_identifier, a.opening_balance,
            a.current_balance, a.balance_date, a.credit_limit,
            a.include_in_net_worth, a.include_in_liquid_assets,
            a.is_protected_reserve, a.is_archived,
        ]
        for a in accounts
    ]
    log_event(db, action="export.accounts_csv", user_id=user.id, request=request)
    db.commit()
    return _csv_response(header, rows, "capitalos_accounts.csv")


# ----------------------------------------------------------------- CSV: goals
@router.get("/goals.csv")
def export_goals_csv(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    goals = db.scalars(
        select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.name)
    ).all()
    header = [
        "id", "name", "description", "target_amount", "currency",
        "target_date", "priority", "goal_type", "manual_contributed_amount",
        "linked_account_ids", "protected", "status",
    ]
    rows = [
        [
            g.id, g.name, g.description, g.target_amount, g.currency,
            g.target_date, g.priority, g.goal_type, g.manual_contributed_amount,
            json.dumps(g.linked_account_ids) if g.linked_account_ids else "",
            g.protected, g.status,
        ]
        for g in goals
    ]
    log_event(db, action="export.goals_csv", user_id=user.id, request=request)
    db.commit()
    return _csv_response(header, rows, "capitalos_goals.csv")


# -------------------------------------------------------------- CSV: holdings
@router.get("/holdings.csv")
def export_holdings_csv(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    holdings = db.scalars(
        select(Holding).where(Holding.user_id == user.id).order_by(Holding.asset_name)
    ).all()
    header = [
        "id", "asset_name", "ticker", "asset_class", "quantity",
        "native_currency", "cost_basis", "latest_unit_price",
        "latest_valuation", "valuation_date", "liquidity_class",
        "include_in_net_worth", "account_id",
    ]
    rows = [
        [
            h.id, h.asset_name, h.ticker, h.asset_class, h.quantity,
            h.native_currency, h.cost_basis, h.latest_unit_price,
            h.latest_valuation, h.valuation_date, h.liquidity_class,
            h.include_in_net_worth, h.account_id,
        ]
        for h in holdings
    ]
    log_event(db, action="export.holdings_csv", user_id=user.id, request=request)
    db.commit()
    return _csv_response(header, rows, "capitalos_holdings.csv")
