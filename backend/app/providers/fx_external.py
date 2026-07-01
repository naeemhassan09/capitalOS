"""External FX rate fetchers (free, key-less sources).

Primary:  open.er-api.com  (ExchangeRate-API open endpoint, 160+ currencies,
          daily updates, includes PKR and SAR which the ECB feed lacks).
Fallback: fawazahmed0 currency-api via jsDelivr CDN.

Only stdlib networking is used (urllib) so no extra dependency is required.
Fetched values are returned as Decimal — never float — keyed by quote currency.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from decimal import Decimal

logger = logging.getLogger("capitalos.fx")

_TIMEOUT_SECONDS = 15
_UA = {"User-Agent": "CapitalOS/1.0 (self-hosted personal finance)"}


class ExternalFxError(RuntimeError):
    """Raised when no external source could provide rates."""


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _from_erapi(base: str, symbols: list[str]) -> dict[str, Decimal]:
    data = _get_json(f"https://open.er-api.com/v6/latest/{base}")
    if data.get("result") != "success":
        raise ExternalFxError(f"er-api returned {data.get('result')!r}")
    rates = data.get("rates") or {}
    out: dict[str, Decimal] = {}
    for sym in symbols:
        if sym in rates:
            # Round-trip through str to avoid binary-float artefacts.
            out[sym] = Decimal(str(rates[sym]))
    return out


def _from_currency_api(base: str, symbols: list[str]) -> dict[str, Decimal]:
    data = _get_json(
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest"
        f"/v1/currencies/{base.lower()}.json"
    )
    rates = data.get(base.lower()) or {}
    out: dict[str, Decimal] = {}
    for sym in symbols:
        val = rates.get(sym.lower())
        if val is not None:
            out[sym] = Decimal(str(val))
    return out


def fetch_latest_rates(base: str, symbols: list[str]) -> tuple[dict[str, Decimal], str]:
    """Return ({quote: rate}, source_name). Tries each source in order."""
    base = base.upper()
    symbols = [s.upper() for s in symbols if s.upper() != base]
    errors: list[str] = []
    for name, fn in (("er-api", _from_erapi), ("currency-api", _from_currency_api)):
        try:
            rates = fn(base, symbols)
            if rates:
                return rates, name
            errors.append(f"{name}: no matching symbols")
        except Exception as exc:  # noqa: BLE001 - network sources fail in many ways
            errors.append(f"{name}: {exc}")
            logger.warning("FX source %s failed: %s", name, exc)
    raise ExternalFxError("; ".join(errors))
