"""External investment price fetchers (free, key-less sources).

A holding's ``ticker`` encodes which market source to use:

- ``PSX:MEBL``           → Pakistan Stock Exchange data portal (dps.psx.com.pk).
- ``MUFAP:<substring>``  → Pakistani mutual-fund NAVs scraped from the daily
                           MUFAP "NAV and Sales Load" table; the part after the
                           prefix is matched case-insensitively against fund
                           names (e.g. ``MUFAP:Meezan Rozana``).
- anything else          → generic quote, e.g. ``AAPL.US`` or ``RYA.IE``.
                           Primary: stooq.com light CSV endpoint.
                           Fallback: Yahoo Finance chart API (a trailing
                           ``.US`` suffix is stripped for Yahoo symbols).

The fetched price is assumed to be quoted in the holding's ``native_currency``
(PSX/MUFAP quote in PKR; stooq/Yahoo quote in the listing currency) — the
caller is responsible for setting that currency correctly on the holding.

Only stdlib networking is used (urllib) so no extra dependency is required.
Prices are returned as Decimal — never float.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from decimal import Decimal, InvalidOperation

logger = logging.getLogger("capitalos.prices")

_TIMEOUT_SECONDS = 15
_UA = {"User-Agent": "CapitalOS/1.0 (self-hosted personal finance)"}

_MUFAP_NAV_URL = "https://www.mufap.com.pk/Industry/IndustryStatDaily?tab=3"
_MUFAP_CACHE_TTL_SECONDS = 15 * 60
# (fetched_at_monotonic, page_html) — the NAV page is ~1 MB, cache it briefly
# so syncing several MUFAP holdings costs a single request.
_mufap_cache: tuple[float, str] | None = None


class PriceError(RuntimeError):
    """Raised when a price could not be fetched for a ticker."""


def _get(url: str, headers: dict[str, str] | None = None) -> str:
    req = urllib.request.Request(url, headers=headers or _UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def _to_decimal(raw: object, context: str) -> Decimal:
    try:
        # Round-trip through str to avoid binary-float artefacts.
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise PriceError(f"{context}: unparseable price {raw!r}") from exc
    if value <= 0:
        raise PriceError(f"{context}: non-positive price {raw!r}")
    return value


# ------------------------------------------------------------------ PSX (PKR)
def fetch_psx(symbol: str) -> tuple[Decimal, str]:
    """Latest traded price from the PSX data portal intraday timeseries.

    ``https://dps.psx.com.pk/timeseries/int/{SYMBOL}`` returns
    ``{"status": 1, "data": [[unix_ts, price, volume], ...]}`` newest-first.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise PriceError("PSX: empty symbol")
    try:
        payload = json.loads(_get(f"https://dps.psx.com.pk/timeseries/int/{symbol}"))
    except PriceError:
        raise
    except Exception as exc:  # noqa: BLE001 - network sources fail in many ways
        raise PriceError(f"PSX: fetch failed for {symbol}: {exc}") from exc
    ticks = payload.get("data") or []
    if payload.get("status") != 1 or not ticks:
        raise PriceError(f"PSX: no data for symbol {symbol}")
    return _to_decimal(ticks[0][1], f"PSX {symbol}"), "psx"


# -------------------------------------------------------------- MUFAP (PKR)
def _mufap_page() -> str:
    global _mufap_cache  # noqa: PLW0603 - simple module-level TTL cache
    now = time.monotonic()
    if _mufap_cache is not None and now - _mufap_cache[0] < _MUFAP_CACHE_TTL_SECONDS:
        return _mufap_cache[1]
    try:
        page = _get(_MUFAP_NAV_URL)
    except Exception as exc:  # noqa: BLE001
        raise PriceError(f"MUFAP source unavailable: {exc}") from exc
    _mufap_cache = (now, page)
    return page


def fetch_mufap(fund_query: str) -> tuple[Decimal, str]:
    """Daily NAV from the MUFAP "NAV and Sales Load" table (HTML scrape).

    Table columns: Sector | AMC | Fund | Category | Inception Date | Offer |
    Repurchase | NAV | Validity Date | ... — the first row whose fund name
    contains ``fund_query`` (case-insensitive) wins.
    """
    query = fund_query.strip().lower()
    if not query:
        raise PriceError("MUFAP: empty fund name")
    page = _mufap_page()
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [
            re.sub(r"<[^>]+>|\s+", " ", cell).strip()
            for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
        ]
        if len(cells) < 8:
            continue
        if query in cells[2].lower():
            return _to_decimal(cells[7], f"MUFAP {cells[2]}"), "mufap"
    raise PriceError(f"MUFAP: no fund matching {fund_query!r}")


# ------------------------------------------------- generic (stooq → yahoo)
def _from_stooq(symbol: str) -> Decimal:
    """Stooq light CSV: Symbol,Date,Time,Open,High,Low,Close,Volume."""
    body = _get(f"https://stooq.com/q/l/?s={symbol.lower()}&f=sd2t2ohlcv&h&e=csv")
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if len(lines) < 2 or "<" in lines[0]:
        raise PriceError(f"stooq: unexpected response for {symbol}")
    fields = lines[1].split(",")
    if len(fields) < 7 or fields[6] in ("", "N/D"):
        raise PriceError(f"stooq: no quote for {symbol}")
    return _to_decimal(fields[6], f"stooq {symbol}")


def _from_yahoo(symbol: str) -> Decimal:
    """Yahoo Finance chart API (key-less). ``AAPL.US`` → Yahoo symbol ``AAPL``."""
    ysym = re.sub(r"\.US$", "", symbol.upper())
    data = json.loads(
        _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?interval=1d&range=1d")
    )
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        raise PriceError(f"yahoo: no data for {symbol}")
    price = (result[0].get("meta") or {}).get("regularMarketPrice")
    if price is None:
        raise PriceError(f"yahoo: no market price for {symbol}")
    return _to_decimal(price, f"yahoo {symbol}")


def fetch_quote(symbol: str) -> tuple[Decimal, str]:
    """Generic listed quote. Tries each source in order (like FX fallbacks)."""
    symbol = symbol.strip()
    if not symbol:
        raise PriceError("empty ticker")
    errors: list[str] = []
    for name, fn in (("stooq", _from_stooq), ("yahoo", _from_yahoo)):
        try:
            return fn(symbol), name
        except Exception as exc:  # noqa: BLE001 - network sources fail in many ways
            errors.append(f"{name}: {exc}")
            logger.warning("Price source %s failed for %s: %s", name, symbol, exc)
    raise PriceError("; ".join(errors))


# ----------------------------------------------------------------- registry
def fetch_price(ticker: str) -> tuple[Decimal, str]:
    """Resolve the market source from the ticker convention and fetch a price.

    Returns ``(price, source_name)``; raises :class:`PriceError` on failure.
    """
    ticker = (ticker or "").strip()
    prefix, _, rest = ticker.partition(":")
    match prefix.upper():
        case "PSX":
            return fetch_psx(rest)
        case "MUFAP":
            return fetch_mufap(rest)
        case _:
            return fetch_quote(ticker)
