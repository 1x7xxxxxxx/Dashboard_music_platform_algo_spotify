"""R586 — the legend's computed place treats a pie's domain and a paper annotation as taken.

Type: Test
Uses: src.dashboard.utils.legend_place, charts.apply_defaults, treasury_chart, trigger_algo
Depends on: nothing
Persists in: nothing

Owner, 2026-10-15: on Trésorerie the legend covered the circle (« l'argent mois par mois » :
en bas à gauche du graphe temporel) ; on Prédiction algos it covered the Discover Weekly
pill. R574 only counted cartesian points — a pie, a gauge and an annotation were empty air.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.dashboard.utils import charts
from src.dashboard.utils.legend_place import (_annotation_box, blocked, least_covered,
                                              occupied_boxes)


def _place(fig) -> str:
    leg = charts.apply_defaults(fig).layout.legend
    return f"{leg.yanchor} {leg.xanchor}"


def test_a_pie_beside_a_flat_series_pushes_the_legend_off_its_side() -> None:
    fig = make_subplots(rows=1, cols=2, column_widths=[0.7, 0.3],
                        specs=[[{"type": "xy"}, {"type": "domain"}]])
    fig.add_trace(go.Scatter(y=[5, 5, 5], name="a"), row=1, col=1)
    fig.add_trace(go.Scatter(y=[4, 4, 4], name="b"), row=1, col=1)
    fig.add_trace(go.Pie(values=[1, 2], showlegend=False), row=1, col=2)
    assert not _place(fig).endswith("right"), _place(fig)


def test_a_paper_pill_top_left_is_not_covered() -> None:
    fig = go.Figure([go.Scatter(y=[10, 5, 1], name="a"), go.Scatter(y=[9, 4, 0], name="b")])
    # without the pill a falling line leaves top right free — put a pill there
    fig.add_annotation(x=1.0, y=0.9, xref="paper", yref="paper", xanchor="right",
                       text="<b>Discover Weekly</b><br>déclenché par : écoutes", showarrow=False)
    assert _place(fig) != "top right", _place(fig)


def test_a_data_annotation_is_not_a_box() -> None:
    fig = go.Figure([go.Scatter(y=[1, 2], name="a")])
    fig.add_annotation(x=1, y=2, text="pic")
    assert occupied_boxes(fig) == []


def test_boxes_never_outweigh_points_inside_a_clear_place() -> None:
    # Every place overlaps the box ⇒ the data count still decides between them.
    fig = go.Figure([go.Scatter(y=[1, 5, 10], name="a"), go.Scatter(y=[0, 4, 9], name="b")])
    fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper", text="<br>".join(["x" * 120] * 20),
                       showarrow=False)
    assert all(blocked(occupied_boxes(fig), p, 2) for p in ("top left", "top right"))
    assert least_covered(fig, 2)[0] == "top left"


def test_the_treasury_legend_sits_bottom_left_of_the_time_chart() -> None:
    from src.dashboard.utils.treasury_chart import cashflow_figure
    rows = [("revenu", "imusician", 30.0, 1), ("revenu", "sacem", 5.0, 1),
            ("depense", "meta_ads", 50.0, -1), ("depense", "distribution", 15.0, -1)]
    cf = pd.DataFrame([{"year": 2025, "month": m, "flux": f, "source": s, "amount_eur": v,
                        "direction": d} for m in range(1, 13) for f, s, v, d in rows])
    assert _place(cashflow_figure(cf)) == "bottom left"


def test_the_algo_legend_never_covers_a_playlist_pill() -> None:
    from tests.test_a_release_target_says_where_it_comes_from import _EST, _three_levers
    from src.dashboard.views.trigger_algo import _release_targets as rt
    readings = {"A": pd.DataFrame({"age_days": [27], "DW": [420.0], "RADIO": [900.0],
                                   "RR": [700.0]})}
    fig = rt.indicators_figure(["A"], _three_levers(300.0, 1000.0),
                               money={"cpr": 0.05, "rate": {}, "est": _EST}, readings=readings)
    n = charts._legend_would_show(fig)
    assert n == 0, "R586: the cohort column names its marks in its header"
    place = least_covered(fig, n)[0]
    pills = [_annotation_box(a) for a in fig.layout.annotations if a.bgcolor]
    assert len(pills) == 3, "one pill per playlist"
    assert not blocked(pills, place, n), place
