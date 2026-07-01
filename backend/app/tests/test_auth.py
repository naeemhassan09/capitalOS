"""Integration tests for the auth flow (require Postgres; skipped if absent)."""

from __future__ import annotations

import pytest

from app.tests.conftest import SETUP_PAYLOAD

pytestmark = pytest.mark.integration


def test_setup_login_me_logout_cycle(client):
    # First-run setup creates the owner and sets the session cookie.
    resp = client.post("/api/v1/auth/setup", json=SETUP_PAYLOAD)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == SETUP_PAYLOAD["email"]
    assert body["is_owner"] is True

    # /me works with the session cookie now held by the client.
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == SETUP_PAYLOAD["email"]

    # Logout requires the CSRF header (session cookie is present).
    from app.core.csrf import CSRF_COOKIE_NAME

    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    out = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert out.status_code == 200

    # After logout the session is revoked.
    me_again = client.get("/api/v1/auth/me")
    assert me_again.status_code == 401


def test_second_setup_is_rejected(client):
    first = client.post("/api/v1/auth/setup", json=SETUP_PAYLOAD)
    assert first.status_code == 201
    # A second setup attempt must be refused (app already initialised).
    second = client.post(
        "/api/v1/auth/setup",
        json={**SETUP_PAYLOAD, "email": "intruder@example.com"},
    )
    assert second.status_code == 409


def test_setup_status_reflects_initialisation(client):
    before = client.get("/api/v1/auth/setup-status")
    assert before.status_code == 200
    assert before.json()["initialized"] is False

    client.post("/api/v1/auth/setup", json=SETUP_PAYLOAD)

    after = client.get("/api/v1/auth/setup-status")
    assert after.json()["initialized"] is True


def test_login_with_wrong_password_is_unauthorised(client):
    client.post("/api/v1/auth/setup", json=SETUP_PAYLOAD)
    # Log out first so we are testing the login path cleanly.
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": SETUP_PAYLOAD["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_login_success_after_setup(client):
    client.post("/api/v1/auth/setup", json=SETUP_PAYLOAD)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": SETUP_PAYLOAD["email"], "password": SETUP_PAYLOAD["password"]},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == SETUP_PAYLOAD["email"]
