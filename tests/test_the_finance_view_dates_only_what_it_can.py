"""R262 — finance: the break-even duration written on the Distributeurs treasury, what one
trigger is worth as a POINT, no date under six months of history, SACEM apart on the home.

Type: Test
Uses: src/dashboard/utils/artist_cashflow.py (break_even), treasury_chart.py
      (breakeven_text, breakeven_figure), views/imusician.py

Code-critic (R262): not a second chart on the forecast page (the treasury lives on
Distributeurs, fiche 63) ; a trigger is a POINT, never an extrapolated line (no cadence of
triggers is measured) ; keep the 12-month pace and add the « fewer than N months → no
date » guard `break_even` lacked.

R488 (owner W11, 2026-10-09): the treasury became `breakeven_figure` — two cumulative
lines on a log axis, the star of one trigger above the revenue line.

Mutation record (2026-09-28) : the `trop_court` branch removed → red ; the trigger drawn
as a line from the last month → red ; imusician no longer passing the verdict → red.
"""
import ast
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.artist_cashflow import MIN_MOIS_POUR_UNE_DATE, break_even
from src.dashboard.utils.treasury_chart import breakeven_figure, breakeven_text

ROOT = Path(__file__).resolve().parents[1]


def _months(n, net):
    d = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=n, freq="MS"),
                      "net": [net] * n})
    d["cumul"] = d["net"].cumsum() - 100
    return d


def test_no_break_even_date_under_the_minimum_history():
    short = break_even(_months(MIN_MOIS_POUR_UNE_DATE - 1, 5.0))
    assert short["etat"] == "trop_court" and short["date"] is None
    assert "trop tôt" in breakeven_text(short)
    enough = break_even(_months(MIN_MOIS_POUR_UNE_DATE, 5.0))
    assert enough["etat"] == "atteint" and enough["mois"] is not None


def _cashflow(n):
    rows = [{"year": 2025, "month": m, "flux": f, "amount_eur": v}
            for m in range(1, n + 1) for f, v in (("revenu", 2.0), ("depense", 50.0))]
    return pd.DataFrame(rows)


def _star(fig):
    return [tr for tr in fig.data if tr.mode == "markers+text"]


def test_a_trigger_is_a_single_point_above_the_revenue_line():
    cf = _cashflow(8)
    fig = breakeven_figure(cf, _months(8, 1.0), trigger=("Un déclenchement vaut", 23.4))
    star = _star(fig)
    assert len(star) == 1 and len(star[0].x) == 1, "a point, never a line"
    assert float(star[0].y[0]) == 8 * 2.0 + 23.4
    assert not _star(breakeven_figure(cf, _months(8, 1.0), trigger=("x", 0))), (
        "no value → no point, never a 0 € star")


def test_the_break_even_reads_on_a_log_axis_without_inventing_a_zero():
    cf = _cashflow(4)
    cf.loc[(cf["month"] == 1) & (cf["flux"] == "revenu"), "amount_eur"] = 0.0
    fig = breakeven_figure(cf, _months(4, 1.0), verdict="v")
    assert fig.layout.yaxis.type == "log", "the spend crushes the revenue on a linear axis"
    assert fig.data[0].y[0] is None, "a 0 € month drawn on a log axis"
    assert any(a.text == "v" for a in fig.layout.annotations), "the verdict is not drawn"


def test_the_cross_view_treasury_carries_the_verdict_and_the_point():
    tree = ast.parse((ROOT / "src/dashboard/views/imusician.py").read_text(encoding="utf-8"))
    kw = {k.arg for n in ast.walk(tree) if isinstance(n, ast.Call)
          and getattr(n.func, "id", "") == "breakeven_figure" for k in n.keywords}
    assert {"verdict", "trigger"} <= kw
