"""Integration tests for accounts and transactions (require Postgres)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _account_payload(**overrides) -> dict:
    payload = {
        "name": "AIB Current",
        "account_type": "current",
        "currency": "EUR",
        "country": "IE",
        "current_balance": "1940.00",
        "opening_balance": "1940.00",
    }
    payload.update(overrides)
    return payload


def test_account_create_list_get_patch_archive(auth_client):
    # Create.
    created = auth_client.post("/api/v1/accounts", json=_account_payload())
    assert created.status_code == 201, created.text
    acc = created.json()
    acc_id = acc["id"]
    assert acc["name"] == "AIB Current"
    assert acc["is_archived"] is False

    # List (should contain the new account).
    listing = auth_client.get("/api/v1/accounts")
    assert listing.status_code == 200
    assert any(a["id"] == acc_id for a in listing.json())

    # Get by id.
    fetched = auth_client.get(f"/api/v1/accounts/{acc_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == acc_id

    # Patch.
    patched = auth_client.patch(
        f"/api/v1/accounts/{acc_id}", json={"name": "AIB Main Current"}
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "AIB Main Current"

    # Archive (soft delete).
    archived = auth_client.delete(f"/api/v1/accounts/{acc_id}")
    assert archived.status_code == 200

    # Archived account is hidden from the default listing.
    listing2 = auth_client.get("/api/v1/accounts")
    assert all(a["id"] != acc_id for a in listing2.json())
    # ...but visible when explicitly requested.
    listing3 = auth_client.get("/api/v1/accounts?include_archived=true")
    assert any(a["id"] == acc_id for a in listing3.json())


def test_account_requires_authentication(client):
    # No session cookie -> 401.
    resp = client.get("/api/v1/accounts")
    assert resp.status_code == 401


def test_transaction_create_and_duplicate_returns_409(auth_client):
    acc = auth_client.post("/api/v1/accounts", json=_account_payload()).json()
    txn_payload = {
        "account_id": acc["id"],
        "booking_date": "2026-06-20",
        "description": "Tesco groceries",
        "amount": "42.50",
        "currency": "EUR",
        "direction": "debit",
        "kind": "expense",
    }
    first = auth_client.post("/api/v1/transactions", json=txn_payload)
    assert first.status_code == 201, first.text

    # Same account + fingerprint inputs -> duplicate rejected.
    dup = auth_client.post("/api/v1/transactions", json=txn_payload)
    assert dup.status_code == 409


def test_transaction_list_returns_created_row(auth_client):
    acc = auth_client.post("/api/v1/accounts", json=_account_payload()).json()
    auth_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "booking_date": "2026-06-21",
            "description": "Salary",
            "amount": "3200.00",
            "currency": "EUR",
            "direction": "credit",
            "kind": "income",
        },
    )
    listing = auth_client.get(f"/api/v1/transactions?account_id={acc['id']}")
    assert listing.status_code == 200
    data = listing.json()
    assert data["total"] == 1
    assert data["items"][0]["description"] == "Salary"
