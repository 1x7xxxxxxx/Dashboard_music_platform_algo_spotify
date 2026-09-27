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


def _daily(df: pd.DataFrame | None, col: str) -> pd.Series:
    """A date-indexed series summed per day, empty when there is nothing measured."""
    if df is None or df.empty:
        return pd.Series(dtype=float)
    s = pd.to_numeric(df[col], errors="coerce").fillna(0)
    s.index = pd.to_datetime(df["date"])
    return s.groupby(level=0).sum().sort_index()


def _crossing_date(days: pd.DatetimeIndex, cs: pd.Series, cr: pd.Series):
    """The day after the LAST day revenue was behind spend, if revenue is ahead at the end."""
    behind = (cr < cs).to_numpy()
    if behind[-1]:
        return None
    if behind.any():
        return days[int(np.flatnonzero(behind)[-1]) + 1]
    spent = np.flatnonzero((cs > 0).to_numpy())
    return days[int(spent[0])] if spent.size else None


def cumulative_breakeven(spend_daily: pd.DataFrame | None,
                         rev_daily: pd.DataFrame | None) -> dict:
    """Breakeven of cumulative revenue against cumulative spend, over the OVERLAP only.

    Returns {'etat', 'date', 'covered_start', 'covered_end', 'timeline'}:

    * 'aucun_recouvrement' — one series is missing, or they never coexist (the last day of
      one precedes the first day of the other). No verdict can be read.
    * 'croise' — `date` is the day revenue moved ahead of spend for the LAST time, and it
      stays ahead up to `covered_end`. A crossing later lost is not a breakeven.
    * 'jamais' — revenue is behind spend at `covered_end`.

    Both cumuls are reset to zero at `covered_start = max(starts)`: revenue earned before
    the first ad euro (or spend before the first reported revenue) is excluded, because it
    would hand one side a head start the comparison did not earn. `covered_end =
    min(ends)`: past it only one series is reported and a flat line is not a zero.

    `timeline` (union of both ranges, daily) carries `cumul_spend` / `cumul_revenue`,
    NaN before `covered_start` and cumulated from it onwards, for the figure.
    """
    s, r = _daily(spend_daily, "spend"), _daily(rev_daily, "revenue_eur")
    out = {"etat": "aucun_recouvrement", "date": None, "covered_start": None,
           "covered_end": None, "timeline": None}
    if s.empty or r.empty:
        return out
    covered_start = max(s.index.min(), r.index.min())
    covered_end = min(s.index.max(), r.index.max())
    out.update(covered_start=covered_start, covered_end=covered_end)
    all_days = pd.date_range(min(s.index.min(), r.index.min()),
                             max(s.index.max(), r.index.max()), freq="D")
    after = all_days[all_days >= covered_start]
    # The zero is RIGHT here, and written as `fillna(0)` so the widened-calendar ratchet
    # (`tests/test_a_figure_never_draws_a_zero_it_did_not_measure.py`) sees it: it feeds
    # a cumsum, and a day without spend adds nothing. What would be wrong is extending a
    # cumul past its last measurement — `covered_end` bounds the verdict for that.
    cs_all = s.reindex(after).fillna(0).cumsum()
    cr_all = r.reindex(after).fillna(0).cumsum()
    out["timeline"] = pd.DataFrame({
        "date": all_days,
        "cumul_spend": cs_all.reindex(all_days).to_numpy(),
        "cumul_revenue": cr_all.reindex(all_days).to_numpy()})
    if covered_start > covered_end:
        return out
    days = after[after <= covered_end]
    date = _crossing_date(days, cs_all.loc[days], cr_all.loc[days])
    out.update(etat="croise" if date is not None else "jamais", date=date)
    return out
