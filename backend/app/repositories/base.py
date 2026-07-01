"""Small helpers for user-scoped queries shared by routers."""

from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_owned_or_404[T](db: Session, model: type[T], entity_id: uuid.UUID, user_id: uuid.UUID) -> T:
    from fastapi import HTTPException

    obj = db.get(model, entity_id)
    if obj is None or getattr(obj, "user_id", None) != user_id:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


def list_owned[T](db: Session, model: type[T], user_id: uuid.UUID) -> list[T]:
    return list(db.scalars(select(model).where(model.user_id == user_id)).all())
