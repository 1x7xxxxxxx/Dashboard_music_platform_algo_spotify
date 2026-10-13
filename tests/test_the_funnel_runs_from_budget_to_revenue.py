"""R556 — the cross view's funnel runs from the euro spent to the euro earned back.

Owner Y2 of 2026-10-13, fiches 44, 43, 128, 22, 23, 39, 26: seven steps, « X % de l'étape
d'avant » on the nested ones only, revenue = streams gained × the measured €/stream, and
two campaigns compared side by side instead of four separate comparison figures.
"""
import ast
from pathlib import Path

from src.dashboard.utils import full_funnel

ROOT = Path(__file__).resolve().parent.parent

_FULL = {"spend": 100.0, "impressions": 20_000, "link_clicks": 400, "arrivals": 200,
         "store_clicks": 100, "streams": 500}


def _by_key(drawn):
    return {s["key"]: s for s in drawn}


def test_seven_steps_end_on_streams_times_the_measured_rate():
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
    assert full_funnel.figure(full_funnel.steps(_FULL, 0.004)).layout.xaxis.type == "log"


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
