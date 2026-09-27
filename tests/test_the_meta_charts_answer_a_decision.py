"""R246 — the Meta charts the owner reviewed on 2026-09-27 answer a decision, honestly."""
import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils import campaign_compare as cc
from src.dashboard.utils.campaign_funnel import audience_flows
from src.dashboard.utils.creative_decisions import add_quadrants


def test_a_stage_that_widens_or_is_unmeasured_leaves_the_chain():
    rows = pd.DataFrame({"song": ["A", "B"], "impressions": [1000, 2000],
                         "link_clicks": [10, 30], "visits": [50, 40], "store_clicks": [20, None]})
    meta = cc.CHAINS[0][2]
    kept, dropped = cc.nested_stages(rows, meta)
    assert kept == ["impressions", "link_clicks"] and not dropped
    widened = rows.assign(link_clicks=[10, 3000])
    assert cc.nested_stages(widened, meta)[1] == ["link_clicks"], "a funnel widened"
    hyp = cc.CHAINS[1][2]
    assert cc.nested_stages(rows, hyp) == (["visits"], ["store_clicks"]), "an unmeasured stage stayed"


def test_ad_clicks_and_smart_link_visits_are_never_chained():
    chains = {key: [c for c, _ in stages] for key, _, stages in cc.CHAINS}
    assert "link_clicks" in chains["meta"] and "visits" in chains["hypeddit"]
    assert not set(chains["meta"]) & set(chains["hypeddit"])


def test_the_track_funnel_sums_its_campaigns():
    data = {"daily": pd.DataFrame({"campaign_name": ["c1", "c1", "c2"], "date": ["d1", "d2", "d1"],
                                   "spend": [1, 1, 1], "impressions": [100, 50, 200],
                                   "link_clicks": [1, 2, 4]}),
            "tracks": pd.DataFrame({"campaign_name": ["c1", "c2"], "song": ["T", "T"]}),
            "store": pd.DataFrame({"song": ["T"], "store_clicks": [3], "visits": [9]})}
    tf = cc.track_funnel(data, pd.DataFrame({"song": ["T"], "gained": [12.0]}))
    row = tf.set_index("song").loc["T"]
    assert row["impressions"] == 350 and row["link_clicks"] == 7 and row["visits"] == 9


def test_audience_effects_are_flows_never_a_cumul():
    days = pd.date_range("2026-01-01", periods=10)
    daily = pd.DataFrame({"day": days, "streams": [10] * 10, "saves": [2] * 10,
                          "playlist_adds": [1] * 10, "followers_level": list(range(100, 110))})
    flows = audience_flows(daily)
    assert len(flows) == 4 and not any("cumul" in k.lower() for k in flows)
    followers = next(v for k, v in flows.items() if "Abonnés" in k)
    assert followers.dropna().round(6).eq(1.0).all(), "a level must move by its daily GAIN"


def test_the_scatter_writes_its_two_decisions():
    fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[0.1, 0.2, 0.3]))
    add_quadrants(fig, pd.DataFrame({"total_spend": [1, 2, 3], "cpr": [0.1, 0.2, 0.3]}))
    texts = " ".join(a.text for a in fig.layout.annotations)
    assert "pousser" in texts and "couper" in texts
    assert len(fig.layout.shapes) == 2
