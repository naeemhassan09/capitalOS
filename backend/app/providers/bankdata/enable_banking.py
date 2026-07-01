"""Enable Banking (enablebanking.com) API client.

Auth model: every request carries a short-lived RS256 JWT signed with the
application's private key. The JWT is built by hand (base64url header/payload +
PKCS1v15-SHA256 signature via ``cryptography``) so no extra dependency such as
PyJWT is needed. Tokens are cached until shortly before expiry.

Only stdlib networking is used (urllib), matching the other providers.
Amounts are surfaced as strings/Decimal by callers — this module never
constructs binary floats from money fields.

SECURITY: the JWT and the private key are never logged.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger("capitalos.bankdata")

BASE_URL = "https://api.enablebanking.com"
_TIMEOUT_SECONDS = 30
_UA = "CapitalOS/1.0 (self-hosted personal finance)"
_JWT_TTL_SECONDS = 3600
_JWT_REFRESH_MARGIN_SECONDS = 300  # renew ~5 min before expiry


class EnableBankingError(RuntimeError):
    """Raised for any Enable Banking API failure (carries the HTTP status)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def is_auth_error(self) -> bool:
        return self.status in (401, 403)


# ----------------------------------------------------------------- JWT (RS256)
def _b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_jwt(
    app_id: str,
    private_key: rsa.RSAPrivateKey,
    *,
    now: int | None = None,
    ttl: int = _JWT_TTL_SECONDS,
) -> str:
    """Build a minimal RS256 JWT as required by the Enable Banking API."""
    issued_at = int(time.time()) if now is None else now
    header = {"typ": "JWT", "alg": "RS256", "kid": app_id}
    payload = {
        "iss": "enablebanking.com",
        "aud": "api.enablebanking.com",
        "iat": issued_at,
        "exp": issued_at + ttl,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))}"
        f".{_b64url(json.dumps(payload, separators=(',', ':')).encode('utf-8'))}"
    )
    signature = private_key.sign(
        signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256()
    )
    return f"{signing_input}.{_b64url(signature)}"


def load_private_key(path: str) -> rsa.RSAPrivateKey:
    with open(path, "rb") as fh:
        key = serialization.load_pem_private_key(fh.read(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise EnableBankingError("Enable Banking private key must be an RSA key")
    return key


# ------------------------------------------------------- account identifiers
def _first_identifier_string(node: object) -> str | None:
    """Depth-first search for the first non-empty identifier-looking string.

    ``account_id`` may hold an ``iban`` (current accounts), a masked PAN under
    ``other.identification`` (cards), or other scheme-specific shapes — so we
    walk the structure defensively, preferring ``iban`` when present.
    """
    if isinstance(node, str):
        return node.strip() or None
    if isinstance(node, dict):
        iban = node.get("iban")
        if isinstance(iban, str) and iban.strip():
            return iban.strip()
        # Common identifier keys first, then anything else.
        preferred = ("identification", "masked_pan", "maskedPan", "bban", "msisdn")
        for key in preferred:
            found = _first_identifier_string(node.get(key))
            if found:
                return found
        for key, value in node.items():
            if key in ("scheme_name", "issuer", "currency", "name", *preferred):
                continue
            found = _first_identifier_string(value)
            if found:
                return found
    if isinstance(node, list):
        for item in node:
            found = _first_identifier_string(item)
            if found:
                return found
    return None


def derive_identifier_masked(account: dict) -> str:
    """Short masked identifier for display — never the full account number.

    IBAN/PAN → last 4 characters prefixed with ``••``; falls back to the
    product or name when no identifier string exists at all.
    """
    ident = _first_identifier_string(account.get("account_id"))
    if ident:
        compact = re.sub(r"[\s-]+", "", ident)
        # Masked PANs often already contain mask characters — keep the tail only.
        tail = compact[-4:]
        return f"••{tail}"
    fallback = account.get("product") or account.get("name") or ""
    return str(fallback)[:64]


def derive_display_name(account: dict, fallback: str = "Bank account") -> str:
    for key in ("name", "product"):
        value = account.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    return fallback


# ------------------------------------------------------------------ the client
class EnableBankingClient:
    """Thin JSON client for the Enable Banking API."""

    def __init__(self, app_id: str, private_key_path: str) -> None:
        if not app_id:
            raise EnableBankingError("Enable Banking is not configured (missing app id)")
        self._app_id = app_id
        self._key_path = private_key_path
        self._key: rsa.RSAPrivateKey | None = None
        self._jwt: str | None = None
        self._jwt_expires_at: float = 0.0

    # ------------------------------------------------------------------ auth
    def _token(self) -> str:
        now = time.time()
        if self._jwt and now < self._jwt_expires_at - _JWT_REFRESH_MARGIN_SECONDS:
            return self._jwt
        if self._key is None:
            self._key = load_private_key(self._key_path)
        issued_at = int(now)
        self._jwt = build_jwt(self._app_id, self._key, now=issued_at)
        self._jwt_expires_at = issued_at + _JWT_TTL_SECONDS
        return self._jwt

    # -------------------------------------------------------------- transport
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        url = f"{BASE_URL}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = None
        headers = {
            "User-Agent": _UA,
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token()}",
        }
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            # Never include the Authorization header / JWT in the error text.
            raise EnableBankingError(
                f"Enable Banking {method} {path} failed: HTTP {exc.code}: {body}",
                status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise EnableBankingError(
                f"Enable Banking {method} {path} unreachable: {exc.reason}"
            ) from exc

    # -------------------------------------------------------------- endpoints
    def get_application(self) -> dict:
        """Application details — cheap request to validate the credentials."""
        return self._request("GET", "/application")

    def list_aspsps(self, country: str) -> list[dict]:
        data = self._request("GET", "/aspsps", params={"country": country.upper()})
        return list(data.get("aspsps") or [])

    def start_auth(
        self,
        *,
        aspsp_name: str,
        aspsp_country: str,
        state: str,
        redirect_url: str,
        valid_days: int = 180,
        psu_type: str = "personal",
    ) -> str:
        """Begin end-user authorization; returns the bank redirect URL."""
        valid_until = datetime.now(UTC) + timedelta(days=valid_days)
        data = self._request(
            "POST",
            "/auth",
            json_body={
                "access": {"valid_until": valid_until.isoformat()},
                "aspsp": {"name": aspsp_name, "country": aspsp_country.upper()},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": psu_type,
            },
        )
        url = data.get("url")
        if not url:
            raise EnableBankingError("Enable Banking /auth returned no redirect url")
        return url

    def create_session(self, code: str) -> dict:
        """Exchange the redirect ``code`` for a session (accounts + session_id)."""
        return self._request("POST", "/sessions", json_body={"code": code})

    def get_session(self, session_id: str) -> dict:
        return self._request("GET", f"/sessions/{urllib.parse.quote(session_id)}")

    def get_balances(self, account_uid: str) -> list[dict]:
        data = self._request(
            "GET", f"/accounts/{urllib.parse.quote(account_uid)}/balances"
        )
        return list(data.get("balances") or [])

    def iter_transactions(self, account_uid: str, date_from: str):
        """Yield transactions from ``date_from``, following continuation keys."""
        continuation_key: str | None = None
        while True:
            params: dict = {"date_from": date_from}
            if continuation_key:
                params["continuation_key"] = continuation_key
            data = self._request(
                "GET",
                f"/accounts/{urllib.parse.quote(account_uid)}/transactions",
                params=params,
            )
            yield from data.get("transactions") or []
            continuation_key = data.get("continuation_key")
            if not continuation_key:
                return
