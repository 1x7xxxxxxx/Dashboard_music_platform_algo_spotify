"""R246 — the Meta charts the owner reviewed on 2026-09-27 answer a decision, honestly."""
import pandas as pd

from src.dashboard.utils import campaign_compare as cc
from src.dashboard.utils.campaign_funnel import audience_flows


def test_audience_effects_are_flows_never_a_cumul():
    days = pd.date_range("2026-01-01", periods=10)
    daily = pd.DataFrame({"day": days, "streams": [10] * 10, "saves": [2] * 10,
                          "playlist_adds": [1] * 10, "followers_level": list(range(100, 110))})
    flows = audience_flows(daily)
    assert len(flows) == 4 and not any("cumul" in lab.lower() for lab, _ in flows.values())
    followers = flows["followers_level"][1]
    assert followers.dropna().round(6).eq(1.0).all(), "a level must move by its daily GAIN"
