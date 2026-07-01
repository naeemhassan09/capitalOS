"""Transaction fingerprinting, rule application and transfer linking."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.money import D
from app.models.category import Category
from app.models.rule import CategorisationRule
from app.models.transaction import Transaction

FINGERPRINT_VERSION = 1
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^A-Z0-9 ]")


def normalize_description(text: str | None) -> str:
    if not text:
        return ""
    up = text.upper()
    up = _PUNCT.sub(" ", up)
    return _WS.sub(" ", up).strip()


def build_fingerprint(
    *,
    account_id: str,
    booking_date: date,
    amount: Decimal | float | str,
    currency: str,
    description: str | None,
    value_date: date | None = None,
    external_id: str | None = None,
    version: int = FINGERPRINT_VERSION,
) -> str:
    """Deterministic, versioned fingerprint for duplicate detection."""
    amt = D(amount).quantize(Decimal("0.0001"))
    parts = [
        f"v{version}",
        str(account_id),
        booking_date.isoformat(),
        value_date.isoformat() if value_date else "",
        f"{amt:f}",
        currency.upper(),
        normalize_description(description),
        (external_id or "").strip(),
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ------------------------------------------------------------- rules engine
def _matches(rule: CategorisationRule, txn: Transaction) -> bool:
    field_map = {
        "description": txn.description or "",
        "original_description": txn.original_description or "",
        "merchant": txn.merchant or "",
        "counterparty": txn.counterparty or "",
    }
    op = rule.operator
    if op == "amount_range":
        amt = D(txn.amount)
        lo = D(rule.amount_min) if rule.amount_min is not None else None
        hi = D(rule.amount_max) if rule.amount_max is not None else None
        if lo is not None and amt < lo:
            return False
        return not (hi is not None and amt > hi)

    haystack = field_map.get(rule.match_field, "").lower()
    needle = (rule.match_value or "").lower()
    if op == "contains":
        return needle in haystack
    if op == "equals":
        return haystack == needle
    if op == "starts_with":
        return haystack.startswith(needle)
    if op == "ends_with":
        return haystack.endswith(needle)
    if op == "regex":
        try:
            return re.search(rule.match_value, field_map.get(rule.match_field, "")) is not None
        except re.error:
            return False
    return False


def load_rules(db: Session, user_id: uuid.UUID) -> list[CategorisationRule]:
    return list(
        db.scalars(
            select(CategorisationRule)
            .where(CategorisationRule.user_id == user_id, CategorisationRule.enabled.is_(True))
            .order_by(CategorisationRule.priority.asc(), CategorisationRule.created_at.asc())
        ).all()
    )


def apply_rules(txn: Transaction, rules: list[CategorisationRule]) -> CategorisationRule | None:
    """Apply the first matching rule (deterministic, priority-ordered)."""
    for rule in rules:
        if rule.account_id is not None and rule.account_id != txn.account_id:
            continue
        if not _matches(rule, txn):
            continue
        if rule.category_id is not None:
            txn.category_id = rule.category_id
        if rule.normalized_merchant:
            txn.merchant = rule.normalized_merchant
        if rule.mark_as_transfer:
            txn.is_transfer = True
            txn.kind = "internal_transfer"
        if rule.mark_as_recurring:
            txn.is_recurring = True
        if rule.set_kind:
            txn.kind = rule.set_kind
        return rule
    return None


def uncategorised_category_id(db: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    cat = db.scalar(
        select(Category).where(
            Category.user_id == user_id, Category.slug == "system-uncategorised"
        )
    )
    return cat.id if cat else None


def signed_delta(amount: Decimal | float | str, direction: str) -> Decimal:
    """Effect of a transaction on its account balance: +credit, -debit."""
    a = D(amount)
    return a if direction == "credit" else -a


def link_transfer(db: Session, debit: Transaction, credit: Transaction) -> uuid.UUID:
    """Mark two transactions as a matched internal transfer pair."""
    group_id = uuid.uuid4()
    for t in (debit, credit):
        t.is_transfer = True
        t.kind = "internal_transfer"
        t.transfer_group_id = group_id
    debit.linked_account_id = credit.account_id
    credit.linked_account_id = debit.account_id
    return group_id
