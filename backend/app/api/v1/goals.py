"""Savings goals CRUD with funding-progress computation."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.goals import compute_goal_progress
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.goal import SavingsGoal
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.common import Message
from app.schemas.goal import (
    GoalCreate,
    GoalOut,
    GoalProgressOut,
    GoalUpdate,
    GoalWithProgress,
)
from app.services.audit import log_event
from app.services.views import goal_view, load_accounts, load_goal_views

router = APIRouter(prefix="/goals", tags=["goals"])


def _serialise_linked(linked: list[uuid.UUID] | None) -> list | None:
    return [str(a) for a in linked] if linked is not None else None


@router.get("", response_model=list[GoalWithProgress])
def list_goals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GoalWithProgress]:
    as_of = date.today()
    goals = list(
        db.scalars(
            select(SavingsGoal)
            .where(SavingsGoal.user_id == user.id)
            .order_by(SavingsGoal.priority, SavingsGoal.name)
        ).all()
    )
    views = {v.id: v for v in load_goal_views(db, user.id)}
    result: list[GoalWithProgress] = []
    for goal in goals:
        view = views.get(str(goal.id))
        if view is None:
            continue
        progress = compute_goal_progress(view, as_of)
        result.append(
            GoalWithProgress(
                goal=GoalOut.model_validate(goal),
                progress=GoalProgressOut.model_validate(progress, from_attributes=True),
            )
        )
    return result


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(
    payload: GoalCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavingsGoal:
    data = payload.model_dump()
    data["linked_account_ids"] = _serialise_linked(data.get("linked_account_ids"))
    goal = SavingsGoal(user_id=user.id, **data)
    db.add(goal)
    db.flush()
    log_event(db, action="goal.create", user_id=user.id, entity_type="savings_goal",
              entity_id=goal.id, request=request, after={"name": goal.name})
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/{goal_id}", response_model=GoalWithProgress)
def get_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalWithProgress:
    goal = get_owned_or_404(db, SavingsGoal, goal_id, user.id)
    accounts = {a.id: a for a in load_accounts(db, user.id)}
    view = goal_view(goal, accounts)
    progress = compute_goal_progress(view, date.today())
    return GoalWithProgress(
        goal=GoalOut.model_validate(goal),
        progress=GoalProgressOut.model_validate(progress, from_attributes=True),
    )


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavingsGoal:
    goal = get_owned_or_404(db, SavingsGoal, goal_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    if "linked_account_ids" in data:
        data["linked_account_ids"] = _serialise_linked(data["linked_account_ids"])
    for key, value in data.items():
        setattr(goal, key, value)
    log_event(db, action="goal.update", user_id=user.id, entity_type="savings_goal",
              entity_id=goal.id, request=request)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", response_model=Message)
def delete_goal(
    goal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    goal = get_owned_or_404(db, SavingsGoal, goal_id, user.id)
    db.delete(goal)
    log_event(db, action="goal.delete", user_id=user.id, entity_type="savings_goal",
              entity_id=goal_id, request=request)
    db.commit()
    return Message(detail="Goal deleted")
