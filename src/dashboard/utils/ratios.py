"""One definition of a cost or rate ratio — CPC, CPM, CPR, CTR — for every view.

Type: Utility
Uses: pandas (the Series form only)
Triggers: views/meta_ads_overview.py, views/meta_creatives.py, views/trigger_algo/_reglages.py
Persists in: nothing

R258 (owner notes L500-510 « une définition par KPI jusqu'au bout » ; critic verdict d :
« trois sites ; une fonction pure de ratio partagée, pas une colonne »). The CPC was
computed three times, three ways: `x / y if y > 0 else nan`, `x / y.where(y != 0)`, and
`x / y if y > 0 else None`. The ratio of SUMS, never the mean of ratios (a CPM is
Σspend / Σimpressions × 1000) — the caller aggregates first, this divides.
An undefined ratio (no clicks, no impressions) is ABSENT — None / NaN — never 0: a zero CPC
would read « free clicks ».
Guard: tests/test_a_ratio_is_defined_once.py.
"""
from __future__ import annotations

import math


def per(numerator, denominator, scale: float = 1.0) -> float | None:
    """`numerator / denominator × scale`, or None when the denominator is 0, absent or NaN."""
    try:
        den = float(denominator)
        num = float(numerator)
    except (TypeError, ValueError):
        return None
    if math.isnan(den) or math.isnan(num) or den <= 0:
        return None
    return num / den * scale


def per_series(numerator, denominator, scale: float = 1.0):
    """The same, element-wise on two pandas Series: NaN where the ratio is undefined."""
    import pandas as pd
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    return (num / den.where(den > 0) * scale).astype(float)
