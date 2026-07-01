"""Security primitives: password hashing, field encryption, signed sessions."""

from __future__ import annotations

import base64
import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import BadSignature, TimestampSigner
from itsdangerous.exc import SignatureExpired

from app.core.config import settings

# --------------------------------------------------------------------- passwords
_ph = PasswordHasher()  # Argon2id defaults are strong and current.


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _ph.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# ------------------------------------------------------------------- encryption
def _fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        if settings.is_production:  # pragma: no cover - guarded by config validation
            raise RuntimeError("ENCRYPTION_KEY is required in production.")
        # Deterministic dev fallback derived from SECRET_KEY so encrypted values
        # remain decryptable across restarts in local development.
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode())


def encrypt_str(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_str(token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


# --------------------------------------------------------------------- sessions
# Server trusts a signed, timestamped session id stored in an HTTP-only cookie.
_signer = TimestampSigner(settings.secret_key)


def sign_session(session_id: str) -> str:
    return _signer.sign(session_id.encode()).decode()


def unsign_session(signed_value: str, max_age: int | None = None) -> str | None:
    try:
        raw = _signer.unsign(
            signed_value.encode(),
            max_age=max_age if max_age is not None else settings.session_max_age,
        )
        return raw.decode()
    except (BadSignature, SignatureExpired):
        return None
