"""Declarative base, common mixins and shared column types."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Money is always stored as fixed-precision Numeric — never binary float.
MONEY = Numeric(20, 4)
RATE = Numeric(20, 8)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
