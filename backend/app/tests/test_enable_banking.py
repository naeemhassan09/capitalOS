"""Enable Banking unit tests: JWT builder, transaction mapper, identifiers.

No network and no database — a throwaway RSA key is generated in-test to
verify the hand-rolled RS256 JWT, and the mapper is exercised on plain dicts.
"""

from __future__ import annotations

import base64
import json
from decimal import Decimal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.providers.bankdata.enable_banking import (
    build_jwt,
    derive_display_name,
    derive_identifier_masked,
)
from app.services.bank_sync import map_bank_transaction, pick_balance


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


# ------------------------------------------------------------------ JWT (RS256)
class TestBuildJwt:
    def test_structure_claims_and_signature(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = 1_750_000_000
        token = build_jwt("test-app-id", key, now=now)

        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))

        assert header == {"typ": "JWT", "alg": "RS256", "kid": "test-app-id"}
        assert payload["iss"] == "enablebanking.com"
        assert payload["aud"] == "api.enablebanking.com"
        assert payload["iat"] == now
        assert payload["exp"] == now + 3600

        # Signature must verify with the public key (PKCS1v15 + SHA256)...
        key.public_key().verify(
            _b64url_decode(signature_b64),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        # ...and fail for a different key.
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        try:
            other.public_key().verify(
                _b64url_decode(signature_b64),
                f"{header_b64}.{payload_b64}".encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            raise AssertionError("signature verified with the wrong key")
        except InvalidSignature:
            pass

    def test_no_padding_in_segments(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = build_jwt("app", key)
        assert "=" not in token


# ------------------------------------------------------------------ tx mapping
def _txn(**overrides) -> dict:
    base = {
        "entry_reference": "REF-123",
        "booking_date": "2026-06-28",
        "value_date": "2026-06-29",
        "transaction_amount": {"amount": "12.34", "currency": "EUR"},
        "credit_debit_indicator": "DBIT",
        "remittance_information": ["TESCO", "DUBLIN"],
        "creditor": {"name": "Tesco Ireland"},
        "debtor": {"name": "Naeem"},
        "status": "BOOK",
    }
    base.update(overrides)
    return base


class TestMapBankTransaction:
    def test_debit_maps_to_expense(self):
        mapped = map_bank_transaction(_txn(), fallback_currency="EUR")
        assert mapped is not None
        assert mapped.direction == "debit"
        assert mapped.kind == "expense"
        assert mapped.amount == Decimal("12.34")
        assert mapped.currency == "EUR"
        assert mapped.description == "TESCO DUBLIN"  # remittance list joined
        assert mapped.counterparty == "Tesco Ireland"  # creditor for debits
        assert mapped.external_id == "REF-123"
        assert mapped.booking_date.isoformat() == "2026-06-28"
        assert mapped.value_date is not None and mapped.value_date.isoformat() == "2026-06-29"

    def test_credit_maps_to_income_with_debtor_counterparty(self):
        mapped = map_bank_transaction(
            _txn(credit_debit_indicator="CRDT"), fallback_currency="EUR"
        )
        assert mapped is not None
        assert mapped.direction == "credit"
        assert mapped.kind == "income"
        assert mapped.counterparty == "Naeem"  # debtor for credits

    def test_negative_amount_becomes_positive_magnitude(self):
        mapped = map_bank_transaction(
            _txn(transaction_amount={"amount": "-50.00", "currency": "EUR"}),
            fallback_currency="EUR",
        )
        assert mapped is not None
        assert mapped.amount == Decimal("50.00")

    def test_pending_is_skipped(self):
        assert map_bank_transaction(_txn(status="PDNG"), fallback_currency="EUR") is None

    def test_description_falls_back_to_counterparty_then_generic(self):
        mapped = map_bank_transaction(
            _txn(remittance_information=[]), fallback_currency="EUR"
        )
        assert mapped is not None
        assert mapped.description == "Tesco Ireland"

        mapped = map_bank_transaction(
            _txn(remittance_information=None, creditor=None), fallback_currency="EUR"
        )
        assert mapped is not None
        assert mapped.description == "Bank transaction"

    def test_missing_currency_uses_account_fallback(self):
        mapped = map_bank_transaction(
            _txn(transaction_amount={"amount": "9.99"}), fallback_currency="eur"
        )
        assert mapped is not None
        assert mapped.currency == "EUR"

    def test_unparseable_rows_are_skipped(self):
        assert map_bank_transaction(_txn(booking_date=None, value_date=None),
                                    fallback_currency="EUR") is None
        assert map_bank_transaction(_txn(transaction_amount={}), fallback_currency="EUR") is None


# --------------------------------------------------------------- identifiers
class TestDeriveIdentifier:
    def test_iban_masked_to_last_four(self):
        account = {"account_id": {"iban": "IE29 AIBK 9311 5212 3456 78"}}
        assert derive_identifier_masked(account) == "••5678"

    def test_card_masked_pan_without_iban(self):
        # AIB credit cards expose a masked CPAN, never an IBAN.
        account = {
            "account_id": {"other": {"identification": "5390 12XX XXXX 4321",
                                     "scheme_name": "CPAN"}},
            "product": "AIB Credit Card",
        }
        assert derive_identifier_masked(account) == "••4321"

    def test_falls_back_to_product_then_name(self):
        assert derive_identifier_masked(
            {"account_id": {}, "product": "Revolut Standard"}
        ) == "Revolut Standard"
        assert derive_identifier_masked({"name": "Everyday"}) == "Everyday"
        assert derive_identifier_masked({}) == ""

    def test_display_name_prefers_name_then_product(self):
        assert derive_display_name({"name": "Main", "product": "Current"}) == "Main"
        assert derive_display_name({"product": "Current"}) == "Current"
        assert derive_display_name({}, fallback="AIB") == "AIB"


# ------------------------------------------------------------------- balances
class TestPickBalance:
    def test_prefers_clbd(self):
        balances = [
            {"balance_amount": {"amount": "10.00", "currency": "EUR"}, "balance_type": "ITAV"},
            {"balance_amount": {"amount": "-42.50", "currency": "EUR"}, "balance_type": "CLBD"},
        ]
        picked = pick_balance(balances)
        assert picked is not None
        assert picked[0] == Decimal("-42.50")  # sign preserved as reported

    def test_falls_back_to_first_parseable(self):
        balances = [
            {"balance_amount": {"amount": None}, "balance_type": "XPCD"},
            {"balance_amount": {"amount": "7.77", "currency": "EUR"}, "balance_type": "ITAV"},
        ]
        picked = pick_balance(balances)
        assert picked is not None
        assert picked[0] == Decimal("7.77")

    def test_empty_returns_none(self):
        assert pick_balance([]) is None
