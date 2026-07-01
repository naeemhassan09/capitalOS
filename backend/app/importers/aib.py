"""AIB (Allied Irish Banks) Ireland CSV statement importer.

Typical AIB export header::

    Posted Account,Posted Transactions Date,Description1,Description2,
    Description3,Debit Amount,Credit Amount,Balance,Posted Currency,
    Transaction Type

AIB uses *separate* debit and credit columns (exactly one is populated per
row) and sometimes splits the narrative across ``Description1/2/3``. Amounts
are euro-formatted; currency defaults to EUR when the column is absent.
"""

from __future__ import annotations

from app.importers.base import BaseTransactionImporter, ImporterError, ParsedRow

_DATE_COLS = ("Posted Transactions Date", "Posted Transaction Date", "Date")
_DEBIT_COLS = ("Debit Amount", "Debit")
_CREDIT_COLS = ("Credit Amount", "Credit")
_CURRENCY_COLS = ("Posted Currency", "Currency")
_TYPE_COLS = ("Transaction Type", "Type")
_DESC_COLS = ("Description", "Description1", "Description2", "Description3")


class AibCsvImporter(BaseTransactionImporter):
    importer_type = "aib_csv"
    display_name = "AIB (Ireland) CSV"
    requires_column_map = False

    @classmethod
    def detect(cls, headers: list[str]) -> bool:
        norm = {h.strip().lower() for h in headers}
        has_date = any(c.lower() in norm for c in _DATE_COLS)
        has_debit = any(c.lower() in norm for c in _DEBIT_COLS)
        has_credit = any(c.lower() in norm for c in _CREDIT_COLS)
        # AIB is uniquely identified by separate debit + credit columns plus a
        # "Posted" date column.
        return has_date and has_debit and has_credit

    def parse(self, file_bytes: bytes, column_map: dict | None = None) -> list[ParsedRow]:
        df = self._use_pandas_read(file_bytes)
        cols = {c.lower(): c for c in df.columns}

        def pick(candidates: tuple[str, ...]) -> str | None:
            for cand in candidates:
                if cand.lower() in cols:
                    return cols[cand.lower()]
            return None

        date_col = pick(_DATE_COLS)
        debit_col = pick(_DEBIT_COLS)
        credit_col = pick(_CREDIT_COLS)
        currency_col = pick(_CURRENCY_COLS)
        type_col = pick(_TYPE_COLS)

        if date_col is None or (debit_col is None and credit_col is None):
            raise ImporterError(
                "File does not look like an AIB export (missing date/amount columns)."
            )

        # Description columns present in this file, in order.
        desc_cols = [cols[c.lower()] for c in _DESC_COLS if c.lower() in cols]

        rows: list[ParsedRow] = []
        for record in df.to_dict(orient="records"):
            booking = self._parse_date(record.get(date_col))
            if booking is None:
                continue  # skip header repeats / blank rows

            debit = self._parse_decimal(record.get(debit_col)) if debit_col else None
            credit = self._parse_decimal(record.get(credit_col)) if credit_col else None

            if credit and credit != 0:
                amount = abs(credit)
                direction = "credit"
            elif debit and debit != 0:
                amount = abs(debit)
                direction = "debit"
            else:
                continue  # zero / empty amount → not a real transaction

            parts = [self._clean(record.get(c)) for c in desc_cols]
            description = " ".join(p for p in parts if p).strip()
            txn_type = self._clean(record.get(type_col)) if type_col else ""
            if not description:
                description = txn_type or "AIB transaction"

            currency = (self._clean(record.get(currency_col)) if currency_col else "") or "EUR"

            rows.append(
                ParsedRow(
                    booking_date=booking,
                    value_date=None,
                    description=description,
                    original_description=description,
                    amount=amount,
                    direction=direction,
                    currency=currency.upper()[:3],
                    merchant=None,
                    external_id=None,
                    raw={k: self._clean(v) for k, v in record.items()},
                )
            )
        return rows
