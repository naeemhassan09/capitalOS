"""Revolut CSV statement importer.

Typical Revolut export header::

    Type,Product,Started Date,Completed Date,Description,Amount,Fee,
    Currency,State,Balance

Revolut uses a *single signed* ``Amount`` column (negative = money out).
Rows that are not ``COMPLETED`` (pending, reverted, declined) are skipped so
they never enter the ledger. The ``Completed Date`` is preferred as the
booking date, falling back to ``Started Date``.
"""

from __future__ import annotations

from app.importers.base import BaseTransactionImporter, ImporterError, ParsedRow


class RevolutCsvImporter(BaseTransactionImporter):
    importer_type = "revolut_csv"
    display_name = "Revolut CSV"
    requires_column_map = False

    @classmethod
    def detect(cls, headers: list[str]) -> bool:
        norm = {h.strip().lower() for h in headers}
        return (
            "started date" in norm
            and "amount" in norm
            and "currency" in norm
        )

    def parse(self, file_bytes: bytes, column_map: dict | None = None) -> list[ParsedRow]:
        df = self._use_pandas_read(file_bytes)
        cols = {c.lower(): c for c in df.columns}

        def col(name: str) -> str | None:
            return cols.get(name.lower())

        started_col = col("Started Date")
        completed_col = col("Completed Date")
        amount_col = col("Amount")
        currency_col = col("Currency")
        desc_col = col("Description")
        state_col = col("State")
        type_col = col("Type")
        fee_col = col("Fee")

        if amount_col is None or (started_col is None and completed_col is None):
            raise ImporterError(
                "File does not look like a Revolut export (missing Amount/Date columns)."
            )

        rows: list[ParsedRow] = []
        for record in df.to_dict(orient="records"):
            state = self._clean(record.get(state_col)).upper() if state_col else "COMPLETED"
            if state and state != "COMPLETED":
                continue  # only settled transactions enter the ledger

            booking = None
            if completed_col:
                booking = self._parse_date(record.get(completed_col))
            if booking is None and started_col:
                booking = self._parse_date(record.get(started_col))
            if booking is None:
                continue

            amount = self._parse_decimal(record.get(amount_col))
            if amount is None or amount == 0:
                continue

            direction = "credit" if amount > 0 else "debit"
            magnitude = abs(amount)

            description = self._clean(record.get(desc_col)) if desc_col else ""
            txn_type = self._clean(record.get(type_col)) if type_col else ""
            if not description:
                description = txn_type or "Revolut transaction"

            currency = (self._clean(record.get(currency_col)) if currency_col else "") or "EUR"

            value_date = None
            if started_col:
                value_date = self._parse_date(record.get(started_col))

            raw = {k: self._clean(v) for k, v in record.items()}
            # Preserve fee for auditability (Revolut charges are a separate field).
            if fee_col:
                fee = self._parse_decimal(record.get(fee_col))
                if fee is not None:
                    raw["_parsed_fee"] = f"{fee:f}"

            rows.append(
                ParsedRow(
                    booking_date=booking,
                    value_date=value_date if value_date != booking else None,
                    description=description,
                    original_description=description,
                    amount=magnitude,
                    direction=direction,
                    currency=currency.upper()[:3],
                    merchant=description or None,
                    external_id=None,
                    raw=raw,
                )
            )
        return rows
