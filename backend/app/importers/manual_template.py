"""Manual-entry template importer.

Provides a fixed, well-known CSV layout that users can download, fill in by
hand (or export from a spreadsheet), and re-upload. Because the layout is
fixed, no column-mapping step is required.

Template columns::

    date,description,amount,currency,direction,category

``amount`` is a positive magnitude and ``direction`` is ``credit`` or
``debit``. If ``direction`` is omitted, a signed ``amount`` (negative = debit)
is also accepted. The ``category`` column is advisory — categorisation rules
still run — and is preserved on the row's raw data.
"""

from __future__ import annotations

from app.importers.base import BaseTransactionImporter, ImporterError, ParsedRow

TEMPLATE_COLUMNS: tuple[str, ...] = (
    "date",
    "description",
    "amount",
    "currency",
    "direction",
    "category",
)


class ManualTemplateImporter(BaseTransactionImporter):
    importer_type = "manual_template"
    display_name = "Manual Template CSV"
    requires_column_map = False

    @classmethod
    def template_csv(cls) -> str:
        """Return the header row (plus one example) for download."""
        header = ",".join(TEMPLATE_COLUMNS)
        example = "2024-01-15,Example coffee shop,4.50,EUR,debit,Eating Out"
        return f"{header}\n{example}\n"

    @classmethod
    def detect(cls, headers: list[str]) -> bool:
        norm = {h.strip().lower() for h in headers}
        required = {"date", "description", "amount"}
        return required.issubset(norm) and "direction" in norm

    def parse(self, file_bytes: bytes, column_map: dict | None = None) -> list[ParsedRow]:
        df = self._use_pandas_read(file_bytes)
        cols = {c.lower(): c for c in df.columns}

        required = {"date", "description", "amount"}
        missing = required - set(cols)
        if missing:
            raise ImporterError(
                f"Template file missing required columns: {', '.join(sorted(missing))}"
            )

        date_col = cols["date"]
        desc_col = cols["description"]
        amount_col = cols["amount"]
        currency_col = cols.get("currency")
        direction_col = cols.get("direction")
        category_col = cols.get("category")

        rows: list[ParsedRow] = []
        for record in df.to_dict(orient="records"):
            booking = self._parse_date(record.get(date_col))
            if booking is None:
                continue

            amount = self._parse_decimal(record.get(amount_col))
            if amount is None or amount == 0:
                continue

            direction_raw = (
                self._clean(record.get(direction_col)).lower() if direction_col else ""
            )
            if direction_raw in ("credit", "debit"):
                direction = direction_raw
                magnitude = abs(amount)
            else:
                # No explicit direction: infer from the sign of amount.
                direction = "credit" if amount > 0 else "debit"
                magnitude = abs(amount)

            description = self._clean(record.get(desc_col)) or "Manual entry"
            currency = (self._clean(record.get(currency_col)) if currency_col else "") or "EUR"

            raw = {k: self._clean(v) for k, v in record.items()}
            if category_col:
                raw["_template_category"] = self._clean(record.get(category_col))

            rows.append(
                ParsedRow(
                    booking_date=booking,
                    value_date=None,
                    description=description,
                    original_description=description,
                    amount=magnitude,
                    direction=direction,
                    currency=currency.upper()[:3],
                    merchant=None,
                    external_id=None,
                    raw=raw,
                )
            )
        return rows
