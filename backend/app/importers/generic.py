"""Generic CSV importer driven by a user-supplied column map.

For banks without a dedicated importer, the UI first asks the user to map their
CSV columns onto logical fields. The ``column_map`` maps *logical field* →
*CSV column name*::

    {
        "date": "Transaction Date",
        "description": "Details",
        "amount": "Amount",          # single signed column, OR ...
        "debit": "Money Out",        # ... separate debit / credit columns
        "credit": "Money In",
        "currency": "Ccy",
        "balance": "Running Balance",
        "merchant": "Merchant",
        "external_id": "Reference",
    }

When ``column_map`` is None the importer cannot parse; callers should first
call :meth:`columns` to obtain the available column names for the mapping step.
"""

from __future__ import annotations

from app.importers.base import BaseTransactionImporter, ImporterError, ParsedRow

_LOGICAL_FIELDS = (
    "date",
    "description",
    "debit",
    "credit",
    "amount",
    "currency",
    "balance",
    "merchant",
    "external_id",
)


class GenericCsvImporter(BaseTransactionImporter):
    importer_type = "generic_csv"
    display_name = "Generic CSV (map columns)"
    requires_column_map = True

    @classmethod
    def detect(cls, headers: list[str]) -> bool:
        # Never auto-detected — it is the explicit fallback chosen by the user.
        return False

    @classmethod
    def logical_fields(cls) -> tuple[str, ...]:
        return _LOGICAL_FIELDS

    def parse(self, file_bytes: bytes, column_map: dict | None = None) -> list[ParsedRow]:
        if not column_map:
            raise ImporterError(
                "Generic importer requires a column map. "
                "Call the preview step with a column_map."
            )

        df = self._use_pandas_read(file_bytes)
        available = {c.lower(): c for c in df.columns}

        def resolve(field: str) -> str | None:
            name = column_map.get(field)
            if not name:
                return None
            actual = available.get(str(name).strip().lower())
            if actual is None:
                raise ImporterError(
                    f"Mapped column '{name}' for '{field}' not found in file."
                )
            return actual

        date_col = resolve("date")
        desc_col = resolve("description")
        amount_col = resolve("amount")
        debit_col = resolve("debit")
        credit_col = resolve("credit")
        currency_col = resolve("currency")
        merchant_col = resolve("merchant")
        external_col = resolve("external_id")

        if date_col is None:
            raise ImporterError("Column map must include a 'date' column.")
        if amount_col is None and debit_col is None and credit_col is None:
            raise ImporterError(
                "Column map must include either 'amount' or 'debit'/'credit'."
            )

        default_currency = str(column_map.get("default_currency", "") or "").upper()[:3]

        rows: list[ParsedRow] = []
        for record in df.to_dict(orient="records"):
            booking = self._parse_date(record.get(date_col))
            if booking is None:
                continue

            if amount_col is not None:
                signed = self._parse_decimal(record.get(amount_col))
                if signed is None or signed == 0:
                    continue
                direction = "credit" if signed > 0 else "debit"
                magnitude = abs(signed)
            else:
                debit = self._parse_decimal(record.get(debit_col)) if debit_col else None
                credit = self._parse_decimal(record.get(credit_col)) if credit_col else None
                if credit and credit != 0:
                    magnitude = abs(credit)
                    direction = "credit"
                elif debit and debit != 0:
                    magnitude = abs(debit)
                    direction = "debit"
                else:
                    continue

            description = self._clean(record.get(desc_col)) if desc_col else ""
            if not description:
                description = "Imported transaction"

            currency = (
                (self._clean(record.get(currency_col)) if currency_col else "")
                or default_currency
                or "EUR"
            )
            merchant = self._clean(record.get(merchant_col)) if merchant_col else ""
            external_id = self._clean(record.get(external_col)) if external_col else ""

            rows.append(
                ParsedRow(
                    booking_date=booking,
                    value_date=None,
                    description=description,
                    original_description=description,
                    amount=magnitude,
                    direction=direction,
                    currency=currency.upper()[:3],
                    merchant=merchant or None,
                    external_id=external_id or None,
                    raw={k: self._clean(v) for k, v in record.items()},
                )
            )
        return rows
