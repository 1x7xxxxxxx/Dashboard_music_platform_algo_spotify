"""SACEM account-statement (.xlsx) parser.

Type: Sub
Uses: pandas (+ openpyxl engine)
Depends on: nothing at import time (pure parsing)
Persists in: nothing (returns rows; the caller upserts into sacem_statement)

The SACEM "Mon relevé de compte" export is a ledger: Date, Libellé, Mouvements (€),
Solde (€). Each line is classified so the app can separate gross royalties
(line_type='repartition') from social charges, TVA, membership fees and bank payouts.
French conventions handled: DD/MM/YYYY dates, comma decimals, thin-space thousands.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

_SHEET = "Mon relevé de compte"
_EXPECTED_COLS = ("date", "libellé", "mouvement", "solde")


def classify_line(libelle: str) -> str:
    """Map a statement line label to a type (pure, unit-testable).
    repartition = gross royalties; charge = social contributions; the rest is context."""
    s = (libelle or "").strip().lower()
    if not s:
        return "other"
    if "repartition" in s or "répartition" in s:
        return "repartition"
    if any(k in s for k in ("csg", "crds", "urssaf", "contribution formation", "cotisation")):
        return "charge"
    if "tva" in s:
        return "tva"
    if "admission" in s or "part sociale" in s:
        return "admission"
    if "virement" in s:
        return "payout"
    if "solde" in s:
        return "balance"
    return "other"


def _to_float(v) -> float:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0
    s = str(v).replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _to_date(v):
    if isinstance(v, (datetime, date)):
        return v.date() if isinstance(v, datetime) else v
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def is_sacem_statement(path_or_buffer) -> bool:
    """True if the workbook looks like a SACEM statement (target sheet present)."""
    try:
        return _SHEET in pd.ExcelFile(path_or_buffer).sheet_names
    except Exception:
        return False


def parse_sacem_xlsx(path_or_buffer) -> list[dict]:
    """Return ledger rows [{line_date, libelle, mouvement_eur, solde_eur, line_type}],
    skipping the header and any row without a parseable date. Raises if the expected
    sheet/columns are absent (never silently returns [] on a structural mismatch)."""
    xl = pd.ExcelFile(path_or_buffer)
    if _SHEET not in xl.sheet_names:
        raise ValueError(f"SACEM sheet '{_SHEET}' absent (sheets: {xl.sheet_names})")
    df = pd.read_excel(xl, sheet_name=_SHEET, header=0)
    if df.shape[1] < 4:
        raise ValueError(f"SACEM statement expects ≥4 columns, got {df.shape[1]}")
    df = df.iloc[:, :4]
    df.columns = ["date", "libelle", "mouvement", "solde"]

    rows = []
    for _, r in df.iterrows():
        d = _to_date(r["date"])
        lib = str(r["libelle"]).strip() if not pd.isna(r["libelle"]) else ""
        if d is None or not lib:
            continue  # header / blank / total lines
        rows.append({
            "line_date": d,
            "libelle": lib,
            "mouvement_eur": round(_to_float(r["mouvement"]), 2),
            "solde_eur": round(_to_float(r["solde"]), 2),
            "line_type": classify_line(lib),
        })
    return rows
