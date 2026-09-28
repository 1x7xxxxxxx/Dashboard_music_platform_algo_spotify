"""R262 — finance: the break-even duration written on the Distributeurs treasury, what one
trigger is worth as a POINT, no date under six months of history, SACEM apart on the home.

Type: Test
Uses: src/dashboard/utils/artist_cashflow.py (break_even), treasury_chart.py
      (breakeven_text, add_trigger_point), views/imusician.py

Code-critic (R262): not a second chart on the forecast page (the treasury lives on
Distributeurs, fiche 63) ; a trigger is a POINT, never an extrapolated line (no cadence of
triggers is measured) ; keep the 12-month pace and add the « fewer than N months → no
date » guard `break_even` lacked.

Mutation record (2026-09-28) : the `trop_court` branch removed → red ; the trigger drawn
as a line from the last month → red ; imusician no longer passing the verdict → red.
"""
import ast
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.artist_cashflow import MIN_MOIS_POUR_UNE_DATE, break_even
from src.dashboard.utils.treasury_chart import add_trigger_point, breakeven_text

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


def test_a_trigger_is_a_single_point_above_the_balance():
    m = _months(8, 1.0)
    fig = go.Figure()
    add_trigger_point(fig, m, "Un déclenchement vaut", 23.4)
    assert len(fig.data) == 1 and len(fig.data[0].x) == 1, "a point, never a line"
    assert float(fig.data[0].y[0]) == float(m["cumul"].iloc[-1]) + 23.4
    empty = go.Figure()
    add_trigger_point(empty, m, "x", 0)
    assert not empty.data, "no value → no point, never a 0 € star"


def test_the_distributeurs_treasury_carries_the_verdict_and_the_point():
    tree = ast.parse((ROOT / "src/dashboard/views/imusician.py").read_text(encoding="utf-8"))
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"breakeven_text", "add_trigger_point", "treasury_figure"} <= calls
    kw = {k.arg for n in ast.walk(tree) if isinstance(n, ast.Call)
          and getattr(n.func, "id", "") == "treasury_figure" for k in n.keywords}
    assert "verdict" in kw
