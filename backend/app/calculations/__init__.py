"""Pure, unit-tested financial calculations.

Functions in this package must not touch the database or FastAPI. They operate
on plain view objects (see ``types.py``) plus an injected currency converter,
which keeps the core financial logic deterministic and testable.
"""
