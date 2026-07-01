"""Backend test suite.

Pure calculation tests run with no database. Integration tests (marked
``integration``) require Postgres and are skipped automatically when a test
database cannot be provisioned — see ``conftest.py``.
"""
