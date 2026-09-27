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


def test_the_cohort_sentence_compares_only_with_enough_campaigns_of_each_kind():
    base = pd.DataFrame({"family": ["engagement"] * 2 + ["trafic"] * 2,
                         "cost_per_gained": [0.1, 0.2, 0.5, 0.7]})
    assert "engagement" in cc.cohort_sentence(base).split("**")[1]
    thin = base.iloc[:3]
    assert "au moins 2" in cc.cohort_sentence(thin)


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
