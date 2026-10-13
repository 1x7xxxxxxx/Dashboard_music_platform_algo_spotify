"""The two ROI verdicts of the budget tab, as pure functions: a spend→revenue fit and a
cumulative breakeven.

Type: Utility
Uses: pandas, numpy, scipy.stats
Depends on: nothing from the app — the caller hands in DataFrames
Triggered by: src/dashboard/views/trigger_algo/_tab_budget_roi.py
Persists in: nothing

Why these live outside the view — measured on 2026-09-26, artist 1
-------------------------------------------------------------------
Both verdicts were computed inline and both asserted more than their data carried:

* the regression ran from TWO points. A line through two points fits them exactly, so
  the page printed R² = 1.000 and p = 0.000 — "perfect, significant correlation" — as an
  artefact of n. Upstream, a `NaN + x` sum had dropped 10 of the 12 usable months; on the
  12 real months the fit is R² = 0.174, p = 0.177: NOT significant, the opposite verdict;
* the breakeven took the FIRST day where cumulative revenue ≥ cumulative spend. Revenue
  had a seven-month head start before the first ad euro, so the test fired on the first
  spend day (0.48 € spent against 3.75 € earned). Spend overtook revenue a month later and
  never came back: 3 087.82 € against 172.62 € at the end of the overlap.

A pure module is testable by execution, and the future single treasury (R212) can import
the same definitions instead of recomputing a third one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# The smallest number of months a spend→revenue line may be fitted on.
# Rationale (degrees of freedom, not tuned on any artist's data): a fit leaves n − 2
# residual degrees of freedom. At 1 or 2 the two-sided 5 % critical t is 12.7 or 4.3, so
# the p-value is decided by one or two residuals; 3 (n = 5) is the first count where it
# falls near 3 and one outlying month no longer decides the verdict alone. n = 2 is the
# degenerate case: zero residuals, R² = 1 and p = 0 by construction.
MIN_FIT_POINTS = 5


def fit_spend_revenue(df: pd.DataFrame | None) -> dict | None:
    """Linear fit of monthly revenue on monthly Meta spend, or None below MIN_FIT_POINTS.

    Only months where BOTH signals are present and positive count: a revenue-only month
    says nothing about what spend produced, and a spend-only month has no measured revenue.
    """
    from scipy import stats as sp_stats

    if df is None or df.empty:
        return None
    valid = df.dropna(subset=["meta_spend", "revenue_eur"])
    valid = valid[(valid["meta_spend"] > 0) & (valid["revenue_eur"] > 0)]
    if len(valid) < MIN_FIT_POINTS:
        return None
    x = valid["meta_spend"].astype(float).to_numpy()
    y = valid["revenue_eur"].astype(float).to_numpy()
    if np.ptp(x) == 0:          # every month spent the same: no slope is identifiable
        return None
    res = sp_stats.linregress(x, y)
    labels = (valid["period_date"].astype(str).str[:7].tolist()
              if "period_date" in valid.columns else None)
    return {"n": int(len(valid)), "slope": float(res.slope),
            "intercept": float(res.intercept), "r2": float(res.rvalue ** 2),
            "p_value": float(res.pvalue), "x": x, "y": y, "labels": labels}


def fit_decision(fit: dict) -> tuple[str, float | None]:
    """R247 (fiche 45, owner 2026-09-27 : « sans équation ni R² ; quelle décision ? »).

    ('none', None) when the link is not significant at 5 % — the only honest reading is
    that the months do not show one; ('pays', slope) when a significant euro of ads brings
    back at least one euro of revenue; ('short', slope) when it brings back less. Pure."""
    if fit["p_value"] >= 0.05 or fit["slope"] <= 0:
        return "none", None
    return ("pays" if fit["slope"] >= 1 else "short"), fit["slope"]


# R553 (owner Y1, fiche 51 absorbed by fiche 25): the overlap break-even
# (`cumulative_breakeven`) left with the algo page's chart; the one break-even left is
# `artist_cashflow.break_even`, drawn by `treasury_chart.breakeven_figure`.
