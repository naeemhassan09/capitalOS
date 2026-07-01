"""Categorisation rules CRUD and rule testing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.rule import CategorisationRule
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.rule import RuleCreate, RuleOut, RuleTestResult, RuleUpdate
from app.services.audit import log_event
from app.services.transactions import _matches

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
def list_rules(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CategorisationRule]:
    stmt = select(CategorisationRule).where(CategorisationRule.user_id == user.id)
    if enabled_only:
        stmt = stmt.where(CategorisationRule.enabled.is_(True))
    stmt = stmt.order_by(CategorisationRule.priority, CategorisationRule.created_at)
    return list(db.scalars(stmt).all())


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(
    payload: RuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CategorisationRule:
    rule = CategorisationRule(user_id=user.id, **payload.model_dump())
    db.add(rule)
    db.flush()
    log_event(db, action="rule.create", user_id=user.id, entity_type="rule",
              entity_id=rule.id, request=request, after={"name": rule.name})
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=RuleOut)
def get_rule(
    rule_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CategorisationRule:
    return get_owned_or_404(db, CategorisationRule, rule_id, user.id)


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: uuid.UUID,
    payload: RuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CategorisationRule:
    rule = get_owned_or_404(db, CategorisationRule, rule_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    log_event(db, action="rule.update", user_id=user.id, entity_type="rule",
              entity_id=rule.id, request=request)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", response_model=Message)
def delete_rule(
    rule_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    rule = get_owned_or_404(db, CategorisationRule, rule_id, user.id)
    db.delete(rule)
    log_event(db, action="rule.delete", user_id=user.id, entity_type="rule",
              entity_id=rule_id, request=request)
    db.commit()
    return Message(detail="Rule deleted")


@router.post("/{rule_id}/test", response_model=RuleTestResult)
def test_rule(
    rule_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleTestResult:
    """Count existing transactions the rule would match (non-mutating)."""
    rule = get_owned_or_404(db, CategorisationRule, rule_id, user.id)
    stmt = select(Transaction).where(Transaction.user_id == user.id)
    if rule.account_id is not None:
        stmt = stmt.where(Transaction.account_id == rule.account_id)
    txns = db.scalars(stmt).all()
    matched = sum(1 for txn in txns if _matches(rule, txn))
    return RuleTestResult(matched_count=matched)
