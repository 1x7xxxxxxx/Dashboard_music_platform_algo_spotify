"""What one CSV import set aside, read and logged (R502).

Type: Utility
Uses: pandas, src/transformers/csv_dialect.py
Triggers: src/dashboard/views/upload_csv.py
Persists in: csv_upload_log.rejected (via caller)

An unreadable cell is counted, never read 0 (Reis & Housley p.363, dead-letter queue).
"""
import json

import pandas as pd

from src.transformers.csv_dialect import read_number


def readable_numbers(df: pd.DataFrame, columns, decimal: str):
    """`columns` read by the shared reader, blank → 0 — or None when one column holds
    no readable value at all (then it is unreadable, not zero: the parser refuses it)."""
    def _cell(value):
        try:
            number = read_number(value, decimal)
        except ValueError:
            return float('nan')
        return 0.0 if number is None else number

    out = pd.DataFrame({c: df[c].map(_cell) for c in columns})
    if len(out) and out.isna().all().any():
        return None
    return out.fillna(0)


def rejected_json(result: dict):
    """`csv_upload_log.rejected` for one file — None when the parse set nothing aside."""
    rejects = result.get('rejects')
    payload = rejects.as_json() if rejects is not None else None
    return None if payload is None else json.dumps(payload, ensure_ascii=False, default=str)
