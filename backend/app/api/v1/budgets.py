"""Budget CRUD and the monthly budget-vs-actual report."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.budget import BudgetCreate, BudgetOut, BudgetReport, BudgetUpdate
from app.schemas.common import Message
from app.services.audit import log_event
from app.services.budgets import build_budget_report

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetOut])
def list_budgets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Budget]:
    return list(db.scalars(select(Budget).where(Budget.user_id == user.id)).all())


@router.get("/report", response_model=BudgetReport)
def budget_report(
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BudgetReport:
    today = date.today()
    return BudgetReport(**build_budget_report(db, user, year or today.year, month or today.month))


@router.post("", response_model=BudgetOut, status_code=201)
def create_budget(
    payload: BudgetCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Budget:
    get_owned_or_404(db, Category, payload.category_id, user.id)
    existing = db.scalar(
        select(Budget).where(
            Budget.user_id == user.id, Budget.category_id == payload.category_id
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A budget for this category already exists.")
    budget = Budget(user_id=user.id, category_id=payload.category_id, amount=payload.amount)
    db.add(budget)
    db.flush()
    log_event(db, action="budget.create", user_id=user.id, entity_type="budget",
              entity_id=budget.id, request=request)
    db.commit()
    db.refresh(budget)
    return budget


@router.patch("/{budget_id}", response_model=BudgetOut)
def update_budget(
    budget_id: uuid.UUID,
    payload: BudgetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Budget:
    budget = get_owned_or_404(db, Budget, budget_id, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(budget, key, value)
    log_event(db, action="budget.update", user_id=user.id, entity_type="budget",
              entity_id=budget.id, request=request)
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}", response_model=Message)
def delete_budget(
    budget_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    budget = get_owned_or_404(db, Budget, budget_id, user.id)
    db.delete(budget)
    log_event(db, action="budget.delete", user_id=user.id, entity_type="budget",
              entity_id=budget_id, request=request)
    db.commit()
    return Message(detail="Budget deleted")
