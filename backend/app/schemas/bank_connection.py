"""Bank connection (open banking) schemas.

Provider session ids and external account uids are encrypted at rest and are
never exposed through list endpoints; discovered-account uids only appear in
the auth-completion / account-discovery responses that feed the mapping UI.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class BankStatusOut(BaseModel):
    configured: bool


class AspspOut(BaseModel):
    name: str
    country: str


class ConnectRequest(BaseModel):
    aspsp_name: str = Field(min_length=1, max_length=120)
    aspsp_country: str = Field(default="IE", min_length=2, max_length=8)


class ConnectResponse(BaseModel):
    url: str
    connection_id: uuid.UUID


class CompleteRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1, max_length=64)


class DiscoveredAccountOut(BaseModel):
    uid: str
    name: str
    identifier_masked: str
    currency: str | None = None


class CompleteResponse(BaseModel):
    connection_id: uuid.UUID
    aspsp_name: str
    accounts: list[DiscoveredAccountOut]


class LinkMapping(BaseModel):
    external_uid: str = Field(min_length=1)
    account_id: uuid.UUID
    display_name: str = Field(default="", max_length=120)
    identifier_masked: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class CreateLinksRequest(BaseModel):
    connection_id: uuid.UUID
    mappings: list[LinkMapping]


class BankAccountLinkOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    display_name: str
    identifier_masked: str | None
    currency: str | None
    enabled: bool
    last_synced_at: datetime | None


class BankConnectionOut(ORMModel):
    id: uuid.UUID
    provider: str
    aspsp_name: str
    aspsp_country: str
    status: str
    valid_until: datetime | None
    last_synced_at: datetime | None
    created_at: datetime
    links: list[BankAccountLinkOut]


class BankSyncResultOut(BaseModel):
    connection_id: uuid.UUID
    accounts_synced: int
    transactions_created: int
    duplicates_skipped: int
    errors: list[str]
