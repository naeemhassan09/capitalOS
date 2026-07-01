"""Sync Enable Banking connections into CapitalOS accounts and transactions.

Rules:
- The bank-reported balance is authoritative: each sync sets the linked
  account's ``current_balance`` to the reported amount (sign as reported) and
  never adjusts the balance per ingested transaction.
- Transactions are ingested idempotently via the (account_id, fingerprint)
  unique index — re-syncing an overlapping window creates no duplicates.
- Pending (PDNG) transactions are skipped; only booked entries are stored.
- Categorisation rules run on every newly ingested transaction.
- Auth failures from the provider mark the connection ``expired``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_str
from app.models.account import Account
from app.models.bank_connection import BankConnection
from app.models.transaction import Transaction
from app.models.user import User
from app.providers.bankdata.enable_banking import EnableBankingClient, EnableBankingError
from app.services.transactions import apply_rules, build_fingerprint, load_rules

logger = logging.getLogger("capitalos.bankdata")

FIRST_SYNC_LOOKBACK_DAYS = 90
RESYNC_OVERLAP_DAYS = 5
PREFERRED_BALANCE_TYPE = "CLBD"  # closing booked


def make_client() -> EnableBankingClient:
    if not settings.enable_banking_configured:
        raise EnableBankingError("Enable Banking is not configured")
    return EnableBankingClient(
        settings.enable_banking_app_id, settings.enable_banking_private_key_path
    )


# ------------------------------------------------------------------- mapping
@dataclass(frozen=True)
class MappedTransaction:
    """Provider transaction normalised to the CapitalOS ledger vocabulary."""

    booking_date: date
    value_date: date | None
    amount: Decimal  # positive magnitude
    currency: str
    direction: str  # credit | debit
    kind: str  # income | expense
    description: str
    counterparty: str | None
    external_id: str | None


def _parse_date(raw: object) -> date | None:
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def map_bank_transaction(txn: dict, *, fallback_currency: str) -> MappedTransaction | None:
    """Map an Enable Banking transaction dict; returns None when skipped."""
    if (txn.get("status") or "BOOK") == "PDNG":
        return None

    booking_date = _parse_date(txn.get("booking_date")) or _parse_date(txn.get("value_date"))
    if booking_date is None:
        return None

    amount_obj = txn.get("transaction_amount") or {}
    try:
        amount = abs(Decimal(str(amount_obj.get("amount"))))
    except (InvalidOperation, ValueError, TypeError):
        return None
    currency = (amount_obj.get("currency") or fallback_currency or "").upper()[:3]

    indicator = (txn.get("credit_debit_indicator") or "").upper()
    direction = "credit" if indicator == "CRDT" else "debit"
    kind = "income" if direction == "credit" else "expense"

    # Counterparty: who the money went to (debit) / came from (credit).
    party = txn.get("creditor") if direction == "debit" else txn.get("debtor")
    counterparty = None
    if isinstance(party, dict):
        name = party.get("name")
        if isinstance(name, str) and name.strip():
            counterparty = name.strip()[:255]

    remittance = txn.get("remittance_information")
    if isinstance(remittance, list):
        description = " ".join(str(p).strip() for p in remittance if str(p).strip())
    elif isinstance(remittance, str):
        description = remittance.strip()
    else:
        description = ""
    description = description or counterparty or "Bank transaction"

    external_id = txn.get("entry_reference")
    if external_id is not None:
        external_id = str(external_id).strip()[:128] or None

    return MappedTransaction(
        booking_date=booking_date,
        value_date=_parse_date(txn.get("value_date")),
        amount=amount,
        currency=currency,
        direction=direction,
        kind=kind,
        description=description[:500],
        counterparty=counterparty,
        external_id=external_id,
    )


def pick_balance(balances: list[dict]) -> tuple[Decimal, str] | None:
    """Prefer the CLBD (closing booked) balance, else the first parseable one."""
    ordered = sorted(
        balances, key=lambda b: 0 if (b.get("balance_type") == PREFERRED_BALANCE_TYPE) else 1
    )
    for entry in ordered:
        amount_obj = entry.get("balance_amount") or {}
        try:
            amount = Decimal(str(amount_obj.get("amount")))
        except (InvalidOperation, ValueError, TypeError):
            continue
        return amount, (amount_obj.get("currency") or "").upper()
    return None


# ---------------------------------------------------------------------- sync
def sync_connection(
    db: Session,
    user: User,
    connection: BankConnection,
    *,
    client: EnableBankingClient | None = None,
) -> dict:
    """Sync balances + transactions for every enabled link of one connection."""
    if connection.status != "active" or not connection.encrypted_session_id:
        raise EnableBankingError("Connection is not active", status=None)
    now = datetime.now(UTC)
    if connection.valid_until is not None and connection.valid_until < now:
        connection.status = "expired"
        db.commit()
        raise EnableBankingError("Bank authorisation has expired", status=401)

    client = client or make_client()
    rules = load_rules(db, user.id)

    accounts_synced = 0
    created = 0
    duplicates = 0
    errors: list[str] = []

    try:
        for link in connection.links:
            if not link.enabled:
                continue
            uid = decrypt_str(link.encrypted_external_uid)
            account = db.get(Account, link.account_id)
            if uid is None or account is None or account.user_id != user.id:
                errors.append(f"link {link.id}: unresolvable account mapping")
                continue

            # --- balance (authoritative, sign as reported by the bank) ---
            picked = pick_balance(client.get_balances(uid))
            if picked is not None:
                account.current_balance = picked[0]
                account.balance_date = date.today()

            # --- transactions ---
            if link.last_synced_at is not None:
                date_from = (link.last_synced_at - timedelta(days=RESYNC_OVERLAP_DAYS)).date()
            else:
                date_from = date.today() - timedelta(days=FIRST_SYNC_LOOKBACK_DAYS)

            existing = set(
                db.scalars(
                    select(Transaction.fingerprint).where(
                        Transaction.account_id == account.id,
                        Transaction.booking_date >= date_from,
                    )
                )
            )
            for raw in client.iter_transactions(uid, date_from.isoformat()):
                mapped = map_bank_transaction(raw, fallback_currency=account.currency)
                if mapped is None:
                    continue
                fingerprint = build_fingerprint(
                    account_id=str(account.id),
                    booking_date=mapped.booking_date,
                    amount=mapped.amount,
                    currency=mapped.currency,
                    description=mapped.description,
                    value_date=mapped.value_date,
                    external_id=mapped.external_id,
                )
                if fingerprint in existing:
                    duplicates += 1
                    continue
                existing.add(fingerprint)
                txn = Transaction(
                    user_id=user.id,
                    account_id=account.id,
                    booking_date=mapped.booking_date,
                    value_date=mapped.value_date,
                    description=mapped.description,
                    counterparty=mapped.counterparty,
                    amount=mapped.amount,
                    currency=mapped.currency,
                    direction=mapped.direction,
                    kind=mapped.kind,
                    status="booked",
                    external_transaction_id=mapped.external_id,
                    fingerprint=fingerprint,
                    source="bank",
                    is_reviewed=False,
                )
                apply_rules(txn, rules)
                db.add(txn)
                created += 1

            link.last_synced_at = now
            accounts_synced += 1
    except EnableBankingError as exc:
        db.rollback()
        if exc.is_auth_error:
            connection.status = "expired"
            db.commit()
            logger.warning(
                "Bank connection %s marked expired (auth error during sync)", connection.id
            )
        raise

    connection.last_synced_at = now
    db.commit()
    return {
        "connection_id": str(connection.id),
        "accounts_synced": accounts_synced,
        "transactions_created": created,
        "duplicates_skipped": duplicates,
        "errors": errors,
    }


def sync_all_users(db: Session) -> None:
    """Best-effort sync of every active connection (daily scheduler entrypoint)."""
    if not settings.enable_banking_configured:
        return
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    for user in users:
        connections = db.scalars(
            select(BankConnection).where(
                BankConnection.user_id == user.id, BankConnection.status == "active"
            )
        ).all()
        for connection in connections:
            try:
                result = sync_connection(db, user, connection)
                logger.info(
                    "Bank sync %s (%s): %d accounts, %d new txns, %d duplicates",
                    connection.aspsp_name,
                    user.email,
                    result["accounts_synced"],
                    result["transactions_created"],
                    result["duplicates_skipped"],
                )
            except EnableBankingError as exc:
                logger.warning(
                    "Bank sync failed for %s (%s): %s", connection.aspsp_name, user.email, exc
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Unexpected bank sync error for %s (%s)", connection.aspsp_name, user.email
                )
                db.rollback()
