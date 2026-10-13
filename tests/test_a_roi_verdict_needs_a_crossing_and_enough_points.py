"""The spend→revenue fit is judged by EXECUTION: it needs enough months.

R553 (2026-10-13): the overlap break-even (fiche 51) and its tests t4-t7 left with the
algo page's chart — fiche 25 on the Trésorerie page is the one break-even.

Type: Test
Uses: pytest, pandas, scipy, streamlit.testing.v1.AppTest
Depends on: src/dashboard/utils/roi_verdicts.py, src/dashboard/utils/kpi_helpers.py,
            src/dashboard/views/trigger_algo/_tab_budget_roi.py
Persists in: nothing (no database — the view runs on a stub)

What was measured (2026-09-26, review base, artists 1 and 18)
--------------------------------------------------------------
* The regression ran on 2 months. A line through two points is exact: the page showed
  R² = 1.000 and p = 0.000, "perfect, significant correlation".
* It ran on 2 months because `distributor_revenue + sacem_revenue` is NaN in every month
  without a SACEM row, and the NaN months were dropped: 10 of 12 usable months vanished.
  On the 12 months the fit is R² = 0.174, p = 0.177: not significant.
* The breakeven took the FIRST day cumulative revenue ≥ cumulative spend. Revenue had a
  seven-month head start (3.75 €) before the first ad euro (0.48 €), so the test fired on
  the first spend day, 2023-08-25. At the end of the overlap spend led 3 087.82 € to
  172.62 €.
* Artist 18: spend 2023-09 → 2024-09, revenue 2025-12 → 2026-04 — no overlap at all, and
  the page still printed a verdict.

Error class: `a-verdict-computed-past-the-end-of-its-evidence` (extended on 2026-09-26 to
the START side and to the correctness of the verdict inside the overlap).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.dashboard.utils.roi_verdicts import (
    MIN_FIT_POINTS,
    fit_spend_revenue,
)

# Artist 1, review base, 2026-09-26: the 12 months with Meta spend AND distributor revenue
# (spend €, revenue €). The two SACEM months — the only ones the NaN sum kept — are
# 2024-04 and 2024-07.
_REAL_MONTHS = [
    ("2023-08-01", 6.94, 0.27), ("2023-09-01", 41.78, 10.01),
    ("2023-10-01", 85.66, 23.38), ("2023-11-01", 180.72, 12.39),
    ("2023-12-01", 316.81, 9.01), ("2024-01-01", 196.23, 6.06),
    ("2024-04-01", 303.41, 17.10), ("2024-05-01", 162.59, 18.56),
    ("2024-06-01", 19.67, 8.15), ("2024-07-01", 310.40, 20.44),
    ("2024-08-01", 706.74, 18.48), ("2024-09-01", 756.87, 16.58),
]


def _months(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["period_date", "meta_spend", "revenue_eur"])


# ── The fit ────────────────────────────────────────────────────────────────


def test_t1_a_fit_on_two_points_is_refused() -> None:
    two = _months([("2024-04-01", 303.41, 17.10), ("2024-07-01", 310.40, 20.44)])
    assert fit_spend_revenue(two) is None, (
        "a line was fitted through 2 points: R² is 1 and p is 0 by construction, and the "
        "page reads that as a perfect, significant correlation.")


def test_t1b_the_shipped_threshold_is_where_the_code_says_it_is() -> None:
    """Boundary on synthetic data WITH variance: n = MIN − 1 refused, n = MIN accepted."""
    rng = np.random.default_rng(7)
    x = np.linspace(10, 500, MIN_FIT_POINTS)
    y = 0.02 * x + rng.normal(0, 3, MIN_FIT_POINTS) + 10
    rows = [(f"2024-{i + 1:02d}-01", float(a), float(b)) for i, (a, b) in enumerate(zip(x, y))]
    assert fit_spend_revenue(_months(rows[:-1])) is None, (
        f"{MIN_FIT_POINTS - 1} months were fitted although MIN_FIT_POINTS = {MIN_FIT_POINTS}")
    fit = fit_spend_revenue(_months(rows))
    assert fit is not None and fit["n"] == MIN_FIT_POINTS
    assert 0 < fit["r2"] < 1


def test_t2_the_twelve_real_months_are_not_significant() -> None:
    fit = fit_spend_revenue(_months(_REAL_MONTHS))
    assert fit is not None and fit["n"] == 12
    assert fit["r2"] == pytest.approx(0.1742, abs=5e-4)
    assert fit["p_value"] == pytest.approx(0.1770, abs=5e-4)
    assert fit["p_value"] > 0.05


def test_t3_a_revenue_month_without_sacem_keeps_its_revenue() -> None:
    """The NaN sum, at the helper that builds the series (not a copy of its formula)."""
    from src.dashboard.utils import kpi_helpers

    class _Db:
        def fetch_df(self, sql, params=None):
            # R212: ONE scan of v_artist_monthly_cashflow returns every column.
            assert "FROM v_artist_monthly_cashflow" in sql
            return pd.DataFrame({"period_date": [pd.Timestamp("2023-09-01")],
                                 "distributor_revenue": [13.03],
                                 "sacem_revenue": [None],
                                 "meta_spend": [41.78],
                                 "other_costs": [None]})

    fn = getattr(kpi_helpers.get_monthly_roi_series, "__wrapped__",
                 kpi_helpers.get_monthly_roi_series)
    df = fn(_Db(), 424242, pd.Timestamp("2023-01-01").date(),
            pd.Timestamp("2024-12-31").date())
    got = df["revenue_eur"].iloc[0]
    assert got == pytest.approx(13.03), (
        f"revenue_eur = {got} for a month with 13.03 € of distributor revenue and no "
        "SACEM row: an absent SACEM source became NaN and erased the month.")
