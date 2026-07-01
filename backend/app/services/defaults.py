"""Default categories and institutions created for a new user."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.household import HouseholdMember
from app.models.institution import Institution

# (Group, is_income, is_essential, [subcategories]) — spec §5.6.
CATEGORY_TREE: list[tuple[str, bool, bool, list[str]]] = [
    ("Income", True, False, [
        "Salary", "Contract income", "Bonus", "Refund", "Interest",
        "Investment income", "Other income",
    ]),
    ("Housing", False, True, [
        "Rent", "Utilities", "Internet", "Home supplies", "Maintenance",
    ]),
    ("Food", False, True, ["Groceries", "Eating out", "Coffee", "Work meals"]),
    ("Transport", False, True, [
        "Public transport", "Taxi", "Fuel", "Car insurance", "Car maintenance",
        "Car tax", "Parking", "Driving lessons", "Driving test",
    ]),
    ("Family", False, True, [
        "Pakistan household", "Children", "School fees", "Gifts", "Spouse",
        "Family healthcare",
    ]),
    ("Health", False, True, [
        "Doctor", "Laboratory", "Medication", "Dental", "Fitness", "Supplements",
    ]),
    ("Financial", False, True, [
        "Credit-card interest", "Bank fees", "Taxes", "Insurance",
    ]),
    ("Lifestyle", False, False, [
        "Clothing", "Electronics", "Entertainment", "Subscriptions", "Personal care",
    ]),
    ("Travel", False, False, [
        "Flights", "Accommodation", "Ground transport", "Travel spending", "Visa",
    ]),
    ("Savings and investments", False, False, [
        "Emergency fund", "Pension contribution", "Mutual fund", "Stock purchase",
        "Other investment",
    ]),
    ("System", False, False, [
        "Internal transfer", "Credit-card payment", "Balance adjustment", "Uncategorised",
    ]),
]

DEFAULT_INSTITUTIONS: list[tuple[str, str, str]] = [
    # (name, country, type)
    ("AIB", "IE", "bank"),
    ("Revolut", "IE", "bank"),
    ("Member First Credit Union", "IE", "credit_union"),
    ("Trading 212", "IE", "broker"),
    ("Standard Chartered Pakistan", "PK", "bank"),
    ("Meezan Bank", "PK", "bank"),
    ("MCB", "PK", "bank"),
    ("Bank Alfalah", "PK", "bank"),
    ("Al Meezan Investments", "PK", "asset_manager"),
    ("Cash", "OTHER", "cash"),
]


def _slugify(*parts: str) -> str:
    return "-".join(
        "".join(c.lower() if c.isalnum() else "-" for c in p).strip("-") for p in parts
    )


def seed_categories(db: Session, user_id: uuid.UUID) -> dict[str, Category]:
    """Create the default category hierarchy. Idempotent per user+slug."""
    existing = {
        c.slug: c
        for c in db.scalars(select(Category).where(Category.user_id == user_id)).all()
    }
    result: dict[str, Category] = dict(existing)
    for order, (group, is_income, essential, subs) in enumerate(CATEGORY_TREE):
        is_system = group == "System"
        parent_slug = _slugify(group)
        parent = existing.get(parent_slug)
        if parent is None:
            parent = Category(
                user_id=user_id,
                name=group,
                slug=parent_slug,
                is_income=is_income,
                is_essential=essential,
                is_system=is_system,
                sort_order=order,
            )
            db.add(parent)
            db.flush()
            result[parent_slug] = parent
        for sub_order, sub in enumerate(subs):
            sub_slug = _slugify(group, sub)
            if sub_slug in existing:
                continue
            child = Category(
                user_id=user_id,
                parent_id=parent.id,
                name=sub,
                slug=sub_slug,
                is_income=is_income,
                is_essential=essential,
                is_system=is_system,
                sort_order=sub_order,
            )
            db.add(child)
            db.flush()
            result[sub_slug] = child
    return result


def seed_institutions(db: Session, user_id: uuid.UUID) -> dict[str, Institution]:
    existing = {
        i.name: i
        for i in db.scalars(select(Institution).where(Institution.user_id == user_id)).all()
    }
    result: dict[str, Institution] = dict(existing)
    for name, country, itype in DEFAULT_INSTITUTIONS:
        if name in existing:
            continue
        inst = Institution(
            user_id=user_id, name=name, country=country, institution_type=itype
        )
        db.add(inst)
        db.flush()
        result[name] = inst
    return result


def seed_self_member(db: Session, user_id: uuid.UUID, display_name: str) -> HouseholdMember:
    existing = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.user_id == user_id,
            HouseholdMember.relationship_type == "self",
        )
    )
    if existing:
        return existing
    member = HouseholdMember(
        user_id=user_id,
        name=display_name,
        relationship_type="self",
        can_login=True,
        linked_user_id=user_id,
    )
    db.add(member)
    db.flush()
    return member


def seed_defaults_for_user(db: Session, user_id: uuid.UUID, display_name: str) -> None:
    seed_categories(db, user_id)
    seed_institutions(db, user_id)
    seed_self_member(db, user_id, display_name)
