"""R234 — « Comparer mes campagnes » : one scale (€ per stream gained) across campaigns.

The owner's funnel questions asked ACROSS campaigns: which one bought an extra stream
cheapest, engagement against traffic, which track turns clicks into streams, the delay
between exposure and listening. The arithmetic is pure and held here on built frames.
"""
import datetime as dt

import pandas as pd

from src.dashboard.utils import campaign_compare as cc
from src.dashboard.utils.campaign_funnel import best_lag

D0 = dt.date(2026, 3, 1)


def _streams(song: str, before: float, during: float, days: int = 10) -> pd.DataFrame:
    rows = [(song, D0 - dt.timedelta(days=i), before) for i in range(1, 29)]
    rows += [(song, D0 + dt.timedelta(days=i), during) for i in range(days)]
    return pd.DataFrame(rows, columns=["song", "date", "streams"])


def _data(camps: list[tuple], streams: pd.DataFrame, objective=None) -> dict:
    daily = pd.DataFrame(
        [(name, d0 + dt.timedelta(days=i), spend / days)
         for name, d0, days, spend, _ in camps for i in range(days)],
        columns=["campaign_name", "date", "spend"])
    return {"daily": daily,
            "objective": pd.DataFrame(objective or [], columns=["campaign_name", "objective"]),
            "tracks": pd.DataFrame([(n, s) for n, _, _, _, s in camps],
                                   columns=["campaign_name", "song"]),
            "streams": streams,
            "store": pd.DataFrame(columns=["song", "store_clicks"])}


def test_the_cost_is_spend_over_streams_gained_above_the_baseline():
    data = _data([("A", D0, 10, 100.0, "T")], _streams("T", 100, 150))
    row = cc.compare(data).iloc[0]
    assert row["gained"] == 500 and abs(row["cost_per_gained"] - 0.2) < 1e-9
    assert not row["overlap"]


def test_no_gain_gives_no_cost_never_a_negative_or_infinite_one():
    row = cc.compare(_data([("A", D0, 10, 100.0, "T")], _streams("T", 100, 80))).iloc[0]
    assert row["gained"] < 0 and pd.isna(row["cost_per_gained"])


def test_two_campaigns_on_one_track_are_flagged_as_overlapping():
    camps = [("A", D0, 10, 100.0, "T"), ("B", D0 + dt.timedelta(days=5), 10, 50.0, "T"),
             ("C", D0 + dt.timedelta(days=200), 5, 10.0, "T")]
    df = cc.compare(_data(camps, _streams("T", 100, 150))).set_index("campaign_name")
    assert df.loc["A", "overlap"] and df.loc["B", "overlap"] and not df.loc["C", "overlap"]


def test_objectives_group_into_families():
    assert cc.objective_family("OUTCOME_ENGAGEMENT") == "engagement"
    assert cc.objective_family("LINK_CLICKS") == "trafic"
    assert cc.objective_family(None) == "autre"


def test_a_track_converts_clicks_into_gained_streams():
    df = pd.DataFrame({"song": ["T", "T", "U"], "gained": [300.0, 100.0, 50.0]})
    store = pd.DataFrame({"song": ["T", "U"], "store_clicks": [200, 0]})
    out = cc.track_conversion(df, store).set_index("song")
    assert out.loc["T", "per_click"] == 2.0 and pd.isna(out.loc["U", "per_click"])


def test_a_flat_budget_has_no_delay_and_a_weak_link_is_not_named():
    days = pd.date_range("2026-03-01", periods=30)
    flat = pd.DataFrame({"date": days, "spend": 10.0, "streams": range(30)})
    assert best_lag(flat, "spend", "streams") is None
    assert cc._lag_text({"lag": 6, "corr": -0.09, "days": 31}) == "—"
    assert cc._lag_text({"lag": 2, "corr": 0.88, "days": 31}) != "—"


def test_two_campaigns_at_the_same_time_on_different_tracks_do_not_overlap():
    camps = [("A", D0, 10, 100.0, "T"), ("B", D0, 10, 50.0, "U")]
    streams = pd.concat([_streams("T", 100, 150), _streams("U", 10, 20)])
    df = cc.compare(_data(camps, streams)).set_index("campaign_name")
    assert not df.loc["A", "overlap"] and not df.loc["B", "overlap"]


def test_a_creative_alone_in_its_campaign_gets_its_streams_and_a_shared_one_does_not():
    """R239: measured where one creative ran alone; never split across creatives."""
    camps = [("A", D0, 10, 100.0, "T"), ("B", D0 + dt.timedelta(days=200), 10, 80.0, "T")]
    streams = pd.concat([_streams("T", 100, 150),
                         _streams("T", 100, 150).assign(
                             date=lambda d: d["date"] + dt.timedelta(days=200))])
    df = cc.compare(_data(camps, streams))
    creatives = pd.DataFrame([("A", "solo", 100.0), ("B", "x", 40.0), ("B", "y", 40.0)],
                             columns=["campaign_name", "creative_name", "spend"])
    alone, split = cc.creative_streams(df, creatives)
    assert list(alone["creative_name"]) == ["solo"] and alone.iloc[0]["gained"] == 500
    assert split == 1


# ── R595: the tracks are sorted bars of streams per click, R577: the ranking is gone ──
def test_the_tracks_are_sorted_bars_of_streams_per_click() -> None:
    import pandas as pd

    tracks = pd.DataFrame({"song": ["a", "b", "c", "d"], "store_clicks": [10, 400, 0, 50],
                           "gained": [30.0, 400.0, 5.0, 150.0],
                           "per_click": [3.0, 1.0, None, 3.0 / 1.5]})
    fig = cc.tracks_figure(tracks)
    assert [tr.type for tr in fig.data] == ["bar"], "one bar trace, no ray behind it"
    bar = fig.data[0]
    assert bar.orientation == "h"
    assert list(bar.y) == ["b", "d", "a"], "best on top: Plotly stacks from the bottom"
    assert "c" not in list(bar.y), "a track with no click has no ratio"
    assert "400" in bar.text[0], "the clicks the ratio rests on are written by its bar"
    assert cc.tracks_figure(tracks.assign(store_clicks=0)) is None


def test_the_campaign_ranking_is_not_rendered() -> None:
    """R577: `render` draws no chart of its own — only the tracks and the creatives' funnel."""
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(cc.render)))
    called = {n.func.id if isinstance(n.func, ast.Name) else n.func.attr
              for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, (ast.Name, ast.Attribute))}
    assert {"_render_tracks", "_render_creative_funnel"} <= called
    assert not called & {"_render_creatives", "plotly_chart"}, called
    assert not hasattr(cc, "_render_creatives"), "R590: « quelle créa a rapporté » is gone"


# ── R590: the second funnel, budget › campaign › ad set › creative ──────────────
def _tree():
    camps = [("A", D0, 10, 100.0, "T"), ("B", D0 + dt.timedelta(days=200), 10, 80.0, "T")]
    streams = pd.concat([_streams("T", 100, 150),
                         _streams("T", 100, 150).assign(
                             date=lambda d: d["date"] + dt.timedelta(days=200))])
    df = cc.compare(_data(camps, streams))
    creatives = pd.DataFrame([("A", "solo", 100.0, 50, True), ("B", "x", 50.0, 10, True),
                              ("B", "y", 30.0, None, False)],
                             columns=["campaign_name", "creative_name", "spend", "results",
                                      "conv"])
    adsets = pd.DataFrame([("solo", "A", "fr"), ("x", "B", "be"), ("y", "B", "be")],
                          columns=["creative_name", "campaign_name", "adset_name"])
    return cc.creative_tree(df, creatives, adsets)


def test_the_creatives_funnel_has_one_box_per_level() -> None:
    tree = _tree().set_index("id")
    assert sorted(tree["level"].value_counts().items()) == [(0, 1), (1, 2), (2, 2), (3, 3)]
    assert tree.loc["B", "spend"] == 80.0 and tree.loc["B › be", "parent"] == "B"
    assert tree.loc["B", "cpr"] == 8.0, "80 € for 10 results"
    assert pd.isna(tree.loc["B › be › y", "cpr"]), "no conversion goal, no CPR"


def test_streams_gained_sit_on_the_campaign_and_on_a_lone_creative_only() -> None:
    tree = _tree().set_index("id")
    assert tree.loc["A › fr › solo", "gained"] == 500 and tree.loc["A", "gained"] == 500
    assert pd.isna(tree.loc["B › be › x", "gained"]), "a shared creative is never split"
    assert pd.isna(tree.loc["B › be", "gained"])


def test_the_creatives_funnel_is_one_icicle_read_top_down() -> None:
    fig = cc.creative_tree_figure(_tree())
    assert len(fig.data) == 1 and fig.data[0].type == "icicle"
    assert fig.data[0].tiling.orientation == "v"
    assert any("CPR 8" in x for x in fig.data[0].text)
    assert any("500 " in x for x in fig.data[0].text)
    assert cc.creative_tree_figure(cc.creative_tree(pd.DataFrame(), None, None)) is None
