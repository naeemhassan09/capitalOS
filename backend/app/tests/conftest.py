"""Shared pytest fixtures.

Two tiers of tests live in this suite:

* **Pure calculation tests** need no fixtures from here — they import the
  ``app.calculations`` package directly and run everywhere.
* **Integration tests** (marked ``@pytest.mark.integration``) exercise the
  FastAPI app against a real Postgres database. We provision a throwaway
  ``<db>_test`` database at session start. If Postgres is unreachable (e.g. no
  database available locally) every integration test is skipped, but the pure
  calc tests still run.

The ``db`` fixture wraps each test in a SAVEPOINT that is rolled back on
teardown, so tests never see each other's writes and the schema is created only
once per session.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# --------------------------------------------------------------------- markers
INTEGRATION = pytest.mark.integration


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: test requires a Postgres database (skipped if unavailable).",
    )


# ---------------------------------------------------------------- test DB URL
def _test_db_url() -> str:
    """Derive the test database URL by appending ``_test`` to the db name."""
    url = make_url(settings.sqlalchemy_url)
    db_name = (url.database or "capitalos")
    if not db_name.endswith("_test"):
        db_name = f"{db_name}_test"
    # NB: URL.__str__ masks the password as '***'; render_as_string keeps it.
    return url.set(database=db_name).render_as_string(hide_password=False)


def _server_url(test_url: str) -> str:
    """URL pointing at the maintenance ``postgres`` database on the same server."""
    return make_url(test_url).set(database="postgres").render_as_string(hide_password=False)


def _create_test_database(test_url: str) -> None:
    """(Re)create the test database. Raises if the server is unreachable."""
    url = make_url(test_url)
    db_name = url.database
    admin = create_engine(_server_url(test_url), isolation_level="AUTOCOMMIT", future=True)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()


# ----------------------------------------------------------- session engine
@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Session-scoped engine bound to a freshly created test database.

    If the database cannot be provisioned (no Postgres), integration tests that
    depend on this fixture are skipped.
    """
    test_url = _test_db_url()
    try:
        _create_test_database(test_url)
    except Exception as exc:  # noqa: BLE001 - any connection failure means "no DB"
        pytest.skip(f"Postgres test database unavailable: {exc}")

    eng = create_engine(test_url, future=True)

    # Import models so every table is registered on Base.metadata, then create.
    import app.models  # noqa: F401  (registers all tables)
    from app.models.base import Base

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine: Engine) -> Iterator[Session]:
    """A transactional Session rolled back after each test via a SAVEPOINT.

    The outer transaction is never committed, so all writes vanish on teardown
    even if application code calls ``session.commit()`` (which only releases the
    inner SAVEPOINT here).
    """
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, autoflush=False,
                               expire_on_commit=False, future=True)
    session = TestSession(join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


# ---------------------------------------------------------------- app client
@pytest.fixture()
def client(db: Session):
    """FastAPI TestClient with ``get_db`` overridden to the test session."""
    from fastapi.testclient import TestClient

    from app.core.db import get_db
    from app.main import app

    def _override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


class _AuthClient:
    """Thin wrapper that automatically attaches the CSRF header on mutations.

    The CSRF middleware enforces the double-submit token whenever a session
    cookie is present, so after login/setup we echo the ``capitalos_csrf``
    cookie in the ``X-CSRF-Token`` header on unsafe methods.
    """

    def __init__(self, client) -> None:
        self._client = client

    def _csrf_headers(self, headers: dict | None) -> dict:
        from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME

        merged = dict(headers or {})
        token = self._client.cookies.get(CSRF_COOKIE_NAME)
        if token and CSRF_HEADER_NAME not in {k.lower() for k in merged}:
            merged["X-CSRF-Token"] = token
        return merged

    def get(self, *args, **kwargs):
        return self._client.get(*args, **kwargs)

    def post(self, *args, headers=None, **kwargs):
        return self._client.post(*args, headers=self._csrf_headers(headers), **kwargs)

    def patch(self, *args, headers=None, **kwargs):
        return self._client.patch(*args, headers=self._csrf_headers(headers), **kwargs)

    def delete(self, *args, headers=None, **kwargs):
        return self._client.delete(*args, headers=self._csrf_headers(headers), **kwargs)

    def put(self, *args, headers=None, **kwargs):
        return self._client.put(*args, headers=self._csrf_headers(headers), **kwargs)

    @property
    def cookies(self):
        return self._client.cookies


SETUP_PAYLOAD = {
    "email": "owner@example.com",
    "password": "sup3r-secret-pw",
    "display_name": "Owner",
    "base_currency": "EUR",
    "timezone": "Europe/Dublin",
}


@pytest.fixture()
def auth_client(client) -> _AuthClient:
    """A client that has completed first-run setup and holds the session cookie."""
    resp = client.post("/api/v1/auth/setup", json=SETUP_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return _AuthClient(client)
