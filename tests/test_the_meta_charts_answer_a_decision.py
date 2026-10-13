"""R246 — the Meta charts the owner reviewed on 2026-09-27 answer a decision, honestly."""
import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils import campaign_compare as cc
from src.dashboard.utils.campaign_funnel import audience_flows
from src.dashboard.utils.creative_decisions import add_quadrants


def test_audience_effects_are_flows_never_a_cumul():
    days = pd.date_range("2026-01-01", periods=10)
    daily = pd.DataFrame({"day": days, "streams": [10] * 10, "saves": [2] * 10,
                          "playlist_adds": [1] * 10, "followers_level": list(range(100, 110))})
    flows = audience_flows(daily)
    assert len(flows) == 4 and not any("cumul" in lab.lower() for lab, _ in flows.values())
    followers = flows["followers_level"][1]
    assert followers.dropna().round(6).eq(1.0).all(), "a level must move by its daily GAIN"


def test_the_scatter_writes_its_two_decisions():
    fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[0.1, 0.2, 0.3]))
    add_quadrants(fig, pd.DataFrame({"total_spend": [1, 2, 3], "cpr": [0.1, 0.2, 0.3]}))
    texts = " ".join(a.text for a in fig.layout.annotations)
    assert "pousser" in texts and "couper" in texts
    assert len(fig.layout.shapes) == 2
