"""One way to write a number on screen — tiles, tables, captions and hover text.

Type: Utility
Uses: src/dashboard/utils/i18n.py (get_lang)
Triggers: every view that prints a number
Persists in: nothing

R260 (owner, 2026-09-27, notes L549 : « KPI avec les mêmes filtres, les mêmes légendes,
même format »). Measured the same day: 156 `st.metric` calls, 12 competing formatters and
74 hand-made thousands separators — `f"{v:,.2f}".replace(",", " ")`. That hack printed
« 1 234.56 » on a FRENCH screen (the decimal point stayed a point) and « 1 234.56 » on an
ENGLISH one (the separator became a space): wrong in both languages. `kpi_helpers.fmt_eur`
printed « 1,234.56 € » everywhere.

Here: French writes « 1 234,56 € » and « 12 % », English « 1,234.56 € » and « 12% ».
An absent value writes « — », never « 0 » and never « nan ».
Guard: tests/test_a_number_is_written_one_way.py (ratchet on the hand-made forms).
"""
from __future__ import annotations

import math


def _lang() -> str:
    try:
        from src.dashboard.utils.i18n import get_lang
        return get_lang()
    except Exception:                                   # noqa: BLE001 — outside Streamlit
        return "fr"


def _absent(v) -> bool:
    try:
        return v is None or (isinstance(v, float) and math.isnan(v)) or bool(v != v)
    except (TypeError, ValueError):
        return False


def num(v, digits: int = 0, *, lang: str | None = None) -> str:
    """`1234.5` → « 1 235 » / « 1,235 » (digits=0), « 1 234,5 » / « 1,234.5 » (digits=1)."""
    if _absent(v):
        return "—"
    text = f"{float(v):,.{digits}f}"
    if (lang or _lang()) == "fr":
        text = text.replace(",", " ").replace(".", ",").replace(" ", " ")
    return text


def eur(v, digits: int = 2, *, lang: str | None = None) -> str:
    """A euro amount, « — » when unknown."""
    return "—" if _absent(v) else f"{num(v, digits, lang=lang)} €"


def pct(v, digits: int = 0, *, lang: str | None = None) -> str:
    """A percentage GIVEN IN PERCENT (12.5 → « 12,5 % » / « 12.5% »)."""
    if _absent(v):
        return "—"
    return f"{num(v, digits, lang=lang)}{' %' if (lang or _lang()) == 'fr' else '%'}"


def table(df, *, container=None, digits: int = 2, **kwargs):
    """Show `df` with its numbers written by this module — THE way a table reaches the screen
    (R260, notes L549 : « même format »). Integers get no decimals, other numbers `digits`,
    an absent value « — ». Guard: tests/test_a_number_is_written_one_way.py (ratchet)."""
    import pandas as pd
    import streamlit as st
    target = container if container is not None else st
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("width", "stretch")
    if df is None or getattr(df, "empty", True):
        return target.dataframe(df, **kwargs)
    fmt = {}
    for col in df.columns:
        if pd.api.types.is_integer_dtype(df[col]):
            fmt[col] = lambda v: num(v, 0)
        elif pd.api.types.is_float_dtype(df[col]):
            fmt[col] = lambda v, d=digits: num(v, d)
    return target.dataframe(df.style.format(fmt, na_rep="—"), **kwargs)
