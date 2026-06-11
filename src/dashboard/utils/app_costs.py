"""Pure engine: expand recurring operating-cost definitions into a monthly series.

Type: Utility
Uses: pandas
Depends on: nothing (no DB, no Streamlit) — unit-testable in isolation
Persists in: — (read model only; rows come from app_operating_costs)

A cost row declares a charge (monthly / yearly / one_off) from start_month until
end_month (None = ongoing). expand_monthly_costs flattens every active row into a
long [month, category, eur] frame so the admin view can stack costs by category and
compute net margin vs MRR. Yearly charges are amortised /12; one_off lands on its
start month only.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

_PERIODS = {"monthly", "yearly", "one_off"}


def _month_floor(d: _dt.date) -> _dt.date:
    return d.replace(day=1)


def _next_month(d: _dt.date) -> _dt.date:
    return _dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)


def _row_monthly_eur(billing_period: str, amount: float) -> float:
    """Per-month contribution of a charge (yearly amortised /12; one_off handled apart)."""
    if billing_period == "yearly":
        return amount / 12.0
    return amount  # monthly, or one_off's single month


def expand_monthly_costs(rows, up_to_month: _dt.date | None = None) -> pd.DataFrame:
    """Flatten cost definitions into a long [month, category, eur] frame.

    rows: iterable of mappings with keys category, amount_eur, billing_period,
          start_month (date), end_month (date|None), active (bool, default True).
    up_to_month: last month to project to (default = today). Ongoing charges
                 (end_month None) run from start_month to up_to_month inclusive.
    Inactive rows and out-of-range months contribute nothing. Returns an empty
    frame with the right columns when there is nothing to show.
    """
    cols = ["month", "category", "eur"]
    if up_to_month is None:
        up_to_month = _dt.date.today()
    up_to = _month_floor(up_to_month)

    records: list[dict] = []
    for r in rows or []:
        if not r.get("active", True):
            continue
        period = r.get("billing_period", "monthly")
        if period not in _PERIODS:
            continue
        amount = float(r.get("amount_eur") or 0.0)
        if amount <= 0:
            continue
        start = r.get("start_month")
        if not start:
            continue
        start = _month_floor(start)
        end = r.get("end_month")
        end = min(_month_floor(end), up_to) if end else up_to
        if start > end:
            continue
        category = r.get("category") or "other"

        if period == "one_off":
            if start <= up_to:
                records.append({"month": start, "category": category, "eur": amount})
            continue

        per_month = _row_monthly_eur(period, amount)
        m = start
        while m <= end:
            records.append({"month": m, "category": category, "eur": per_month})
            m = _next_month(m)

    if not records:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame.from_records(records)
    # Collapse duplicate (month, category) pairs (several rows of the same category).
    return df.groupby(["month", "category"], as_index=False)["eur"].sum()


def monthly_total(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a long cost frame to [month, eur] total across categories."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["month", "eur"])
    return df.groupby("month", as_index=False)["eur"].sum().sort_values("month")


def current_month_cost(rows, month: _dt.date | None = None) -> float:
    """Total cost charged in `month` (default current). Used for the net-margin metric."""
    if month is None:
        month = _dt.date.today()
    m = _month_floor(month)
    df = expand_monthly_costs(rows, up_to_month=m)
    if df.empty:
        return 0.0
    return float(df[df["month"] == m]["eur"].sum())
