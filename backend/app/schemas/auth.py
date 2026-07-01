"""Auth and user schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    base_currency: str = Field(default="EUR", min_length=3, max_length=3)
    timezone: str = Field(default="Europe/Dublin")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str
    base_currency: str
    timezone: str
    locale: str
    is_owner: bool
    totp_enabled: bool
    last_login_at: datetime | None = None


class SetupStatus(BaseModel):
    initialized: bool
    pin_enabled: bool = False


class SetPinRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    pin: str = Field(pattern=r"^\d{4,8}$")


class PinLoginRequest(BaseModel):
    pin: str = Field(pattern=r"^\d{4,8}$")


class SessionOut(ORMModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    current: bool = False
