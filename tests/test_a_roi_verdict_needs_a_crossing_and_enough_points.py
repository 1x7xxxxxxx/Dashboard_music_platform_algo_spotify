"""The ROI tab's two verdicts are judged by EXECUTION: a fit needs enough months, and a
breakeven is a crossing from below that holds, inside the overlap of both series.

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
    cumulative_breakeven,
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


# ── The breakeven ─────────────────────────────────────────────────────────


def _spend(start: str, end: str, total: float, first: float = 0.48) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D")
    rest = (total - first) / (len(days) - 1)
    return pd.DataFrame({"date": days, "spend": [first] + [rest] * (len(days) - 1)})


def _rev(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["date", "revenue_eur"]).assign(
        date=lambda d: pd.to_datetime(d["date"]))


def _artist1_shape() -> tuple[pd.DataFrame, pd.DataFrame]:
    """3.75 € earned before the first ad euro, then spend runs away."""
    spend = _spend("2023-08-25", "2024-09-30", 3087.82)
    months = pd.date_range("2023-09-01", "2026-04-01", freq="MS")
    rev = _rev([("2023-01-01", 3.75)] + [(d, 13.0) for d in months])
    return spend, rev


def test_t4_a_head_start_is_not_a_breakeven() -> None:
    spend, rev = _artist1_shape()
    be = cumulative_breakeven(spend, rev)
    assert be["etat"] == "jamais", (
        f"verdict {be['etat']} on {be['date']}: revenue earned before the first ad euro "
        "was counted as a return on it.")
    assert be["covered_start"] == pd.Timestamp("2023-08-25")
    assert be["covered_end"] == pd.Timestamp("2024-09-30")
    tl = be["timeline"].set_index("date")
    assert tl.loc["2024-09-30", "cumul_spend"] == pytest.approx(3087.82)
    assert np.isnan(tl.loc["2023-08-24", "cumul_revenue"]), (
        "the cumul is drawn before the overlap starts")


def _two_crossings(hold: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Spend 10 €/day for 60 days; revenue lands in lumps that cross, fall behind, and
    (if `hold`) cross again and stay ahead."""
    spend = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=60, freq="D"),
                          "spend": 10.0})
    lumps = [("2024-01-01", 0.0), ("2024-01-10", 200.0)]      # ahead from 01-10 (cs=100)
    if hold:
        lumps += [("2024-02-05", 600.0)]                     # behind 01-21..02-04, ahead again
    lumps += [("2024-02-29", 0.0)]
    return spend, _rev(lumps)


def test_t5_the_date_is_the_last_crossing_that_holds() -> None:
    be = cumulative_breakeven(*_two_crossings(hold=True))
    assert be["etat"] == "croise"
    assert be["date"] == pd.Timestamp("2024-02-05"), (
        f"breakeven {be['date']}: the FIRST crossing was taken, and it was lost on "
        "2024-01-21 — only the last crossing that holds to the end is a breakeven.")


def test_t5b_a_crossing_later_lost_is_not_a_breakeven() -> None:
    be = cumulative_breakeven(*_two_crossings(hold=False))
    assert be["etat"] == "jamais", (
        f"verdict {be['etat']} on {be['date']}: revenue crossed on 2024-01-10 and fell "
        "behind for good on 2024-01-21.")


def test_t6_an_empty_overlap_gives_no_verdict() -> None:
    spend = _spend("2023-09-01", "2024-09-30", 900.0)
    rev = _rev([(d, 5.0) for d in pd.date_range("2025-12-01", "2026-04-01", freq="MS")])
    be = cumulative_breakeven(spend, rev)
    assert be["etat"] == "aucun_recouvrement", (
        f"verdict {be['etat']} over two series that never coexist (spend ends "
        "2024-09-30, revenue starts 2025-12-01).")
    assert be["date"] is None


# ── The page binds the helper ─────────────────────────────────────────────

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import numpy as np
import pandas as pd
from src.dashboard.views.trigger_algo._tab_budget_roi import _show_breakeven

spend_days = pd.date_range("2023-08-25", "2024-09-30", freq="D")
rest = (3087.82 - 0.48) / (len(spend_days) - 1)
SPEND = pd.DataFrame({{"date": spend_days,
                      "spend": [0.48] + [rest] * (len(spend_days) - 1)}})
months = pd.date_range("2023-09-01", "2026-04-01", freq="MS")
REV = pd.DataFrame({{"date": [pd.Timestamp("2023-01-01")] + list(months),
                    "revenue_eur": [3.75] + [13.0] * len(months)}})

class Db:
    def fetch_df(self, sql, params=None):
        if "v_meta_daily" in sql:
            return SPEND.copy()
        if "revenue" in sql:
            return REV.copy()
        return pd.DataFrame(columns=["date", "popularity"])

_show_breakeven(Db(), "Some Track", 1, None)
"""


def test_t7_the_page_does_not_announce_a_head_start_as_breakeven() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=str(Path(__file__).resolve().parents[1])))
    at.run(timeout=60)
    assert not at.exception, f"the breakeven section raised: {at.exception}"
    assert not [w for w in at.warning if "indisponible" in w.value
                or "unavailable" in w.value], [w.value for w in at.warning]
    assert not list(at.success), (
        f"the page announced {[s.value for s in at.success]} on data where spend "
        "overtakes revenue a month after the first ad euro and never falls behind again.")
    assert len(at.warning) == 1, [w.value for w in at.warning]
    assert len(at.caption) == 2, (
        "both bounds of the verdict (start and end of the overlap) must be stated: "
        f"{[c.value for c in at.caption]}")
