"""R556 — the cross view's funnel runs from the euro spent to the euro earned back.

Owner Y2 of 2026-10-13, fiches 44, 43, 128, 22, 23, 39, 26: seven steps, « X % de l'étape
d'avant » on the nested ones only, revenue = streams gained × the measured €/stream, and
two campaigns compared side by side instead of four separate comparison figures.
"""
import ast
from pathlib import Path

from src.dashboard.utils import full_funnel

ROOT = Path(__file__).resolve().parent.parent

_FULL = {"spend": 100.0, "impressions": 20_000, "reach": 9_000, "link_clicks": 400, "arrivals": 200,
         "store_clicks": 100, "streams": 500}


def _by_key(drawn):
    return {s["key"]: s for s in drawn}


def test_eight_steps_end_on_streams_times_the_measured_rate():
    drawn = full_funnel.steps(_FULL, 0.004)
    assert [s["key"] for s in drawn] == [k for k, _, _ in full_funnel.STEPS]
    assert _by_key(drawn)["revenue"]["value"] == 2.0


def test_streams_are_never_a_share_of_the_platform_clicks():
    streams = _by_key(full_funnel.steps(_FULL, 0.004))["streams"]["text"]
    assert "%" not in streams and "5,0" in streams


def test_an_unmeasured_step_is_not_drawn_and_breaks_the_chain():
    drawn = _by_key(full_funnel.steps({**_FULL, "arrivals": None}, None))
    assert "arrivals" not in drawn and "revenue" not in drawn
    assert "%" not in drawn["store_clicks"]["text"]


def test_under_two_steps_there_is_no_figure():
    assert full_funnel.figure(full_funnel.steps({"spend": 10.0}, None)) is None


def test_the_funnel_is_a_funnel_wide_to_narrow():
    """R589 — ONE funnel, every step in order: the budget is the top case, then
    impressions, reach, clicks, visits, smart-link clicks, streams, revenue."""
    fig = full_funnel.figure(full_funnel.steps(_FULL, 0.004))
    assert fig.data[0].type == "funnel" and len(fig.data) == 1
    assert list(fig.data[0].y) == [full_funnel._label(k) for k in (
        "budget", "impressions", "reach", "link_clicks", "arrivals", "store_clicks",
        "streams", "revenue")]
    w = list(fig.data[0].x)
    assert w[0] == 100 and all(a >= b for a, b in zip(w, w[1:])), w
    assert not fig.layout.annotations, "no step left outside the funnel"
    assert fig.data[0].textfont.size >= 15 and fig.layout.yaxis.tickfont.size >= 14


def test_an_unmeasured_reach_keeps_the_clicks_share_of_impressions():
    drawn = _by_key(full_funnel.steps({**_FULL, "reach": 0}, None))
    assert "reach" not in drawn and "2,0 %" in drawn["link_clicks"]["text"]


def test_each_campaign_name_is_boxed_behind_its_colour():
    from src.dashboard.utils.campaign_pair import PAIR_COLORS
    from src.dashboard.views.meta_x_spotify import campaign_badge
    for i in (0, 1):
        b = campaign_badge("<Été> 2026", i)
        assert f"border:2px solid {PAIR_COLORS[i]}" in b and f"background:{PAIR_COLORS[i]}" in b
        assert "&lt;Été&gt; 2026" in b
    pair = _defs("src/dashboard/views/meta_x_spotify.py")["_render_pair"]
    assert "campaign_badge" in {ast.unparse(n.func) for n in ast.walk(pair)
                                if isinstance(n, ast.Call)}


def test_widths_never_widen_and_keep_a_small_step_visible():
    assert full_funnel.widths([100_000, 2_000, 3_000, 40]) == sorted(
        full_funnel.widths([100_000, 2_000, 3_000, 40]), reverse=True)
    assert min(full_funnel.widths([100_000, 1])) >= 8


def _defs(rel: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_two_campaigns_are_drawn_side_by_side():
    pair = _defs("src/dashboard/views/meta_x_spotify.py")["_render_pair"]
    calls = {ast.unparse(n.func) for n in ast.walk(pair) if isinstance(n, ast.Call)}
    assert "st.columns" in calls and "_funnel_figure" in calls, calls


def test_the_four_comparison_figures_are_gone():
    assert "_render_track_funnel" not in _defs("src/dashboard/utils/campaign_compare.py")
    assert not {"render_campaign_stats", "_render_campaign_series"} & set(
        _defs("src/dashboard/views/hypeddit.py"))
