"""Categories CRUD returning a full hierarchical tree."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.category import Category
from app.models.user import User
from app.repositories.base import get_owned_or_404
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.common import Message
from app.services.audit import log_event


def _slugify(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")


def _to_node(category: Category) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        parent_id=category.parent_id,
        name=category.name,
        slug=category.slug,
        icon=category.icon,
        color=category.color,
        is_essential=category.is_essential,
        is_system=category.is_system,
        is_income=category.is_income,
        sort_order=category.sort_order,
        created_at=category.created_at,
        updated_at=category.updated_at,
        children=[],
    )


def _build_tree(categories: list[Category]) -> list[CategoryOut]:
    """Assemble ordered parent/child tree from a flat, pre-sorted list."""
    by_id: dict[uuid.UUID, CategoryOut] = {c.id: _to_node(c) for c in categories}
    roots: list[CategoryOut] = []
    for cat in categories:
        node = by_id[cat.id]
        if cat.parent_id is not None and cat.parent_id in by_id:
            by_id[cat.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CategoryOut]:
    stmt = (
        select(Category)
        .where(Category.user_id == user.id)
        .order_by(Category.sort_order, Category.name)
    )
    categories = list(db.scalars(stmt).all())
    return _build_tree(categories)


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Category:
    data = payload.model_dump()
    if data.get("parent_id") is not None:
        get_owned_or_404(db, Category, data["parent_id"], user.id)
    slug = data.pop("slug", None) or _slugify(data["name"])
    category = Category(user_id=user.id, slug=slug, **data)
    db.add(category)
    db.flush()
    log_event(db, action="category.create", user_id=user.id, entity_type="category",
              entity_id=category.id, request=request, after={"name": category.name})
    db.commit()
    db.refresh(category)
    return category


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Category:
    return get_owned_or_404(db, Category, category_id, user.id)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Category:
    category = get_owned_or_404(db, Category, category_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("parent_id") is not None:
        if data["parent_id"] == category.id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        get_owned_or_404(db, Category, data["parent_id"], user.id)
    if "slug" in data and not data["slug"]:
        data["slug"] = _slugify(data.get("name") or category.name)
    for key, value in data.items():
        setattr(category, key, value)
    log_event(db, action="category.update", user_id=user.id, entity_type="category",
              entity_id=category.id, request=request)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", response_model=Message)
def delete_category(
    category_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    category = get_owned_or_404(db, Category, category_id, user.id)
    if category.is_system:
        raise HTTPException(status_code=400, detail="System categories cannot be deleted")
    db.delete(category)
    log_event(db, action="category.delete", user_id=user.id, entity_type="category",
              entity_id=category_id, request=request)
    db.commit()
    return Message(detail="Category deleted")
