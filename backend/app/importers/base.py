"""Base classes and shared parsing helpers for CSV transaction importers.

Every bank-specific importer subclasses :class:`BaseTransactionImporter` and
produces a list of :class:`ParsedRow` — a normalized, source-agnostic
representation of a single transaction. Downstream services (fingerprinting,
duplicate detection, rules) operate purely on ``ParsedRow`` and never need to
know which bank a file came from.

Parsing is intentionally defensive: bank exports are messy, inconsistent, and
locale-dependent. The helpers here tolerate a wide range of date and number
formats and never execute file contents — CSV bytes are only ever *read* with
pandas, never evaluated.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

# Date formats we attempt, in order. Day-first formats come first because the
# supported banks (AIB Ireland, Revolut EU) export day-first dates.
_DATE_FORMATS: tuple[str, ...] = (
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d/%m/%y",
    "%m/%d/%Y",
    "%Y/%m/%d",
)

# Currency symbols / prefixes stripped before decimal parsing.
_CURRENCY_JUNK = str.maketrans(
    "", "", "€£$¥₹₨﻿ \t\r\n"
)  # € £ $ ¥ ₹ ₨ + BOM/whitespace


@dataclass(slots=True)
class ParsedRow:
    """A single normalized transaction extracted from an import file.

    ``amount`` is always a positive magnitude; the sign lives in ``direction``.
    ``raw`` preserves the original row for audit / debugging (stored on the
    resulting Transaction's ``raw_data``).
    """

    booking_date: date
    description: str
    original_description: str
    amount: Decimal
    direction: str  # "credit" | "debit"
    currency: str
    value_date: date | None = None
    merchant: str | None = None
    external_id: str | None = None
    raw: dict = field(default_factory=dict)


class ImporterError(ValueError):
    """Raised when a file cannot be parsed by the selected importer."""


class BaseTransactionImporter:
    """Abstract base for all CSV importers.

    Subclasses set :attr:`importer_type` / :attr:`display_name` and implement
    :meth:`parse`. Optionally override :meth:`detect` for header-based
    auto-detection and set :attr:`requires_column_map` when the UI must present
    a column-mapping step before a preview can run.
    """

    importer_type: str = "base"
    display_name: str = "Base Importer"
    requires_column_map: bool = False

    # ------------------------------------------------------------------ API
    @classmethod
    def detect(cls, headers: list[str]) -> bool:
        """Return True if this importer recognises the given header row."""
        return False

    def parse(
        self, file_bytes: bytes, column_map: dict | None = None
    ) -> list[ParsedRow]:
        raise NotImplementedError

    def columns(self, file_bytes: bytes) -> list[str]:
        """Return the CSV header columns (for the UI mapping step)."""
        df = self._use_pandas_read(file_bytes, nrows=0)
        return [str(c) for c in df.columns]

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _use_pandas_read(file_bytes: bytes, nrows: int | None = None) -> pd.DataFrame:
        """Read CSV bytes into a DataFrame, trying utf-8 then latin-1.

        Everything is read as string (``dtype=str``) so we control all numeric
        and date parsing ourselves — pandas' inference is locale-unaware and
        would silently mangle amounts like ``1.234,56``.
        """
        last_err: Exception | None = None
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(
                    io.BytesIO(file_bytes),
                    dtype=str,
                    keep_default_na=False,
                    na_filter=False,
                    nrows=nrows,
                    skip_blank_lines=True,
                    encoding=encoding,
                )
                # Normalise header whitespace.
                df.columns = [str(c).strip() for c in df.columns]
                return df
            except (UnicodeDecodeError, pd.errors.ParserError) as exc:
                last_err = exc
                continue
        raise ImporterError(f"Could not read CSV file: {last_err}")

    @staticmethod
    def _parse_date(value: object) -> date | None:
        """Parse a date from many bank formats. Returns None if empty/unknown."""
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        # Drop a trailing time component if present ("2024-01-05 13:22:01").
        # First try full ISO (handles "2024-01-05T13:22:01Z" etc.).
        iso_candidate = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso_candidate).date()
        except ValueError:
            pass
        # Then explicit formats against the date portion only.
        # Try each explicit format against the full text first (so space-
        # separated formats like "%d %b %Y" match), then against the leading
        # date token if the cell carries a trailing time component.
        head = text.split("T")[0].strip()
        for candidate in (text, head, head.split(" ")[0].strip()):
            for fmt in _DATE_FORMATS:
                try:
                    return datetime.strptime(candidate, fmt).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _parse_decimal(value: object) -> Decimal | None:
        """Parse a monetary amount, tolerating currency symbols and locales.

        Handles thousands separators, comma decimal separators, and parentheses
        as negative (accounting notation). Returns None for blank cells.
        """
        if value is None:
            return None
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        text = str(value).strip()
        if not text:
            return None

        negative = False
        # Accounting-style negatives: (123.45)
        if text.startswith("(") and text.endswith(")"):
            negative = True
            text = text[1:-1]
        # Trailing/leading sign or 'CR'/'DR' markers.
        upper = text.upper()
        if upper.endswith("CR"):
            text = text[:-2].strip()
        elif upper.endswith("DR"):
            negative = True
            text = text[:-2].strip()
        if text.startswith("-"):
            negative = not negative
            text = text[1:]
        elif text.startswith("+"):
            text = text[1:]

        text = text.translate(_CURRENCY_JUNK)
        if not text:
            return None

        # Resolve decimal vs thousands separators.
        if "," in text and "." in text:
            # Whichever appears last is the decimal separator.
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            # Comma only: decimal if it looks like "12,34"; else thousands.
            parts = text.split(",")
            if len(parts[-1]) == 2 and all(p.isdigit() for p in parts):
                text = text.replace(",", ".")
            else:
                text = text.replace(",", "")

        try:
            result = Decimal(text)
        except InvalidOperation:
            return None
        return -result if negative else result

    @staticmethod
    def _clean(value: object) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split()).strip()
