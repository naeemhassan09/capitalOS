"""Pure tests for transaction fingerprinting and description normalisation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.transactions import build_fingerprint, normalize_description

ACCOUNT = "11111111-1111-1111-1111-111111111111"
DAY = date(2026, 6, 20)


def _fp(**kw) -> str:
    base = {
        "account_id": ACCOUNT, "booking_date": DAY, "amount": Decimal("12.34"),
        "currency": "EUR", "description": "Tesco Store 1234",
    }
    base.update(kw)
    return build_fingerprint(**base)


def test_same_inputs_same_hash():
    assert _fp() == _fp()


def test_hash_is_64_char_hex():
    fp = _fp()
    assert len(fp) == 64
    int(fp, 16)  # raises if not hex


def test_different_description_different_hash():
    assert _fp(description="Tesco Store 1234") != _fp(description="Lidl Store 9999")


def test_different_amount_different_hash():
    assert _fp(amount=Decimal("12.34")) != _fp(amount=Decimal("12.35"))


def test_different_account_different_hash():
    other = "22222222-2222-2222-2222-222222222222"
    assert _fp() != _fp(account_id=other)


def test_amount_type_does_not_change_hash():
    # Decimal, float and string forms of the same value normalise identically.
    assert _fp(amount=Decimal("12.34")) == _fp(amount=12.34) == _fp(amount="12.34")


def test_description_normalisation_ignores_case_punctuation_whitespace():
    # Punctuation and repeated whitespace collapse; case is folded.
    assert _fp(description="TESCO   STORE-1234") == _fp(description="tesco store 1234")


def test_version_is_part_of_the_payload():
    assert _fp(version=1) != _fp(version=2)


def test_external_id_distinguishes_otherwise_identical_rows():
    assert _fp(external_id="A") != _fp(external_id="B")


def test_normalize_description_basic():
    assert normalize_description("  Café  #12! ") == "CAF 12"
    assert normalize_description(None) == ""
    assert normalize_description("") == ""
