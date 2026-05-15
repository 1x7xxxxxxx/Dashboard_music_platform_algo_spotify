"""
Type: Utility
Uses: streamlit
Depends on: nothing (pure UI helper)
Persists in: nothing

Generic Streamlit UI helpers shared across views.

`show_empty_state` factors the early-exit pattern repeated ~20+ times across
views:  `if df.empty: st.info(...); return`  →  `if show_empty_state(df, msg): return`
"""
from __future__ import annotations

import streamlit as st

_LEVELS = frozenset({"info", "warning", "error"})


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
