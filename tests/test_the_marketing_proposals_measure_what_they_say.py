"""The R282 proposals compute what their titles claim (tools/dev/charts_dossier/proposals.py).

A proposal is judged by the owner on its picture; the three calculations under the pictures
are pinned here on series whose answer is known by construction.

Does not cover: the SQL (it runs on the review snapshot only), nor the drawing — the PNGs are
looked at before the dossier is sent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev" / "charts_dossier"))

import proposals  # noqa: E402

_DAYS = pd.date_range("2024-01-01", periods=120, freq="D")


def test_the_lag_is_found_where_the_streams_follow_the_spend():
    spend = pd.Series(0.0, index=_DAYS)
    spend.iloc[[20, 50, 80]] = 100.0
    streams = pd.Series(100.0, index=_DAYS)
    streams.iloc[[23, 53, 83]] = 400.0            # three days after each spend
    corr = proposals.lag_correlation(spend, streams)
    assert int(corr.idxmax()) == 3


def test_a_campaign_lift_is_during_minus_before_and_its_price_follows():
    streams = pd.Series(10.0, index=_DAYS)
    streams.loc["2024-03-01":"2024-03-10"] = 30.0
    camp = pd.DataFrame([{"campaign_name": "A", "start": pd.Timestamp("2024-03-01"),
                          "end": pd.Timestamp("2024-03-10"), "spend": 50.0}])
    row = proposals.campaign_uplift(camp, streams).iloc[0]
    assert row["lift"] == 20.0                     # 30/day during, 10/day before
    assert row["cost_per_extra_stream"] == 50.0 / 200.0


def test_a_campaign_followed_by_a_drop_has_no_price_per_stream():
    streams = pd.Series(30.0, index=_DAYS)
    streams.loc["2024-03-01":"2024-03-10"] = 10.0
    camp = pd.DataFrame([{"campaign_name": "B", "start": pd.Timestamp("2024-03-01"),
                          "end": pd.Timestamp("2024-03-10"), "spend": 50.0}])
    assert proposals.campaign_uplift(camp, streams).iloc[0]["cost_per_extra_stream"] is None


def test_fatigue_counts_weeks_from_each_ads_own_launch():
    ads = pd.DataFrame({"ad_id": ["a"] * 14 + ["b"] * 7,
                        "day": list(_DAYS[:14]) + list(_DAYS[30:37]),
                        "clicks": [2] * 7 + [1] * 7 + [2] * 7,
                        "impressions": [100] * 21})
    w = proposals.ad_fatigue(ads).set_index("week")
    assert w.loc[0, "ads"] == 2 and w.loc[1, "ads"] == 1
    assert w.loc[0, "ctr"] == 2.0 and w.loc[1, "ctr"] == 1.0
