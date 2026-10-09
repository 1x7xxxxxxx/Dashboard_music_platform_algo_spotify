"""R474 — a bar label drawn OUTSIDE its bar is never clipped by the plot edge.

Type: Test
Uses: src/dashboard/utils/charts.py (apply_defaults — the drawing door, R243)
Depends on: plotly
Persists in: nothing

Apple Music showed « 686 » as « 68 » (W7, 2026-10-09): `textposition="outside"` with the
default `cliponaxis=True`, and an autorange that leaves no room for the text, so the
longest bar lost its last digits. The sweep found 7 sites (apple_music ×2, airflow_kpi,
revenue_forecast, sacem waterfall, trigger_algo/_tab_reglages ×2): the fix lives in the
door every figure goes through, not in each view.
"""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pytest

from src.dashboard.utils import charts


def _top(**trace):
    fig = px.bar(x=[686, 477, 84], y=["Je ne parle pas", "Saloon", "Remix"],
                 orientation="h", text=[686, 477, 84])
    fig.update_traces(texttemplate="%{text:,.0f}", **trace)
    return fig


@pytest.mark.parametrize("pos", ["outside", "auto"])
def test_the_door_unclips_an_outside_label(pos):
    fig = charts.apply_defaults(_top(textposition=pos))
    assert fig.data[0].cliponaxis is False, f"{pos} label still clipped by the axis"


def test_the_value_axis_leaves_room_for_the_longest_label():
    fig = charts.apply_defaults(_top(textposition="outside"))
    lo, hi = fig.layout.xaxis.range
    assert lo == 0 and hi > 686 * 1.1, (lo, hi)


def test_a_waterfall_and_a_vertical_bar_are_covered():
    wf = charts.apply_defaults(go.Figure(go.Waterfall(x=["a", "b"], y=[10, 5],
                                                      textposition="outside")))
    assert wf.data[0].cliponaxis is False
    v = charts.apply_defaults(go.Figure(go.Bar(x=["a", "b"], y=[100, 3], text=[100, 3],
                                               textposition="outside")))
    assert v.data[0].cliponaxis is False and v.layout.yaxis.range[1] > 110


def test_the_door_respects_what_the_figure_chose():
    inside = charts.apply_defaults(_top(textposition="inside"))
    assert inside.data[0].cliponaxis is None, "an inside label needs nothing"
    fixed = _top(textposition="outside")
    fixed.update_layout(xaxis_range=[0, 2000])
    assert list(charts.apply_defaults(fixed).layout.xaxis.range) == [0, 2000], \
        "overrode a range the figure set"
    neg = charts.apply_defaults(go.Figure(go.Bar(x=["a", "b"], y=[-5, 8], text=[-5, 8],
                                                 textposition="outside")))
    assert neg.layout.yaxis.range is None, "a negative bar must keep its autorange"
