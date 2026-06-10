"""
Type: Utility
Uses: streamlit
Depends on: i18n (t)
Persists in: nothing

Generic Streamlit UI helpers shared across views.

`show_empty_state` factors the early-exit pattern repeated ~20+ times across
views:  `if df.empty: st.info(...); return`  →  `if show_empty_state(df, msg): return`
"""
from __future__ import annotations

from datetime import date as _date

import streamlit as st

from src.dashboard.utils.i18n import t

_LEVELS = frozenset({"info", "warning", "error"})


def smart_date_range(label, min_date, max_date, *, key):
    """Data-bounded period selector. Returns (from_date, to_date) as date objects.

    "Smart" = the choices are derived from the actual data span [min_date, max_date],
    so the user can never land on an empty window (the classic "last 6 months" trap
    when the data is older). Presets: full history, one entry per calendar year
    actually covered, and a custom range bounded to [min, max]. Default = full span.

    Returns (None, None) when min/max are None (no data). Accepts date or datetime.
    """
    if min_date is None or max_date is None:
        return None, None
    min_d = min_date.date() if hasattr(min_date, "date") else min_date
    max_d = max_date.date() if hasattr(max_date, "date") else max_date
    if min_d > max_d:
        min_d, max_d = max_d, min_d

    custom_label = t("ui.custom_range", "Plage personnalisée")
    presets = {t("ui.full_history", "Tout l'historique"): (min_d, max_d)}
    for y in range(min_d.year, max_d.year + 1):
        start, end = max(_date(y, 1, 1), min_d), min(_date(y, 12, 31), max_d)
        if start <= end:
            presets[t("ui.year_n", "Année {y}").format(y=y)] = (start, end)
    presets[custom_label] = None

    choice = st.selectbox(label, list(presets.keys()), key=f"{key}_preset")
    if choice != custom_label:
        return presets[choice]

    rng = st.date_input(
        t("ui.range", "Plage"), value=(min_d, max_d), min_value=min_d, max_value=max_d,
        key=f"{key}_range",
    )
    if isinstance(rng, (tuple, list)) and len(rng) == 2:
        return rng[0], rng[1]
    return min_d, max_d  # single-date mid-selection → fall back to full span


def show_empty_state(df, message: str, *, level: str = "info") -> bool:
    """Render `message` and return True when `df` is empty/None.

    Caller stays in control of the early return:
        if show_empty_state(df, "Aucune donnée."): return

    `level` ∈ {info, warning, error} (validated — never arbitrary attr).
    """
    if level not in _LEVELS:
        raise ValueError(f"show_empty_state: level '{level}' not in {sorted(_LEVELS)}")
    if df is None or getattr(df, "empty", True):
        getattr(st, level)(message)
        return True
    return False
