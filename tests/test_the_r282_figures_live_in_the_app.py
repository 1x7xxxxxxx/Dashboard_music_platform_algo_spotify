"""R301 — the owner's R282 proposals B and D, kept on my recommendation, live in the app.

Type: Test
Uses: pytest, pandas
Depends on: src/dashboard/utils/meta_impact.py (event_study, spend_around),
            src/dashboard/views/hypeddit.py (ring_label)
Persists in: nothing

B — the streams AROUND each wave of campaigns, as an index on the 28 days before it: the one
figure saying how long an effect lasts. Drawn on the Meta Ads page with the SAME waves and
baseline floor as the per-wave verdict (one definition, moved from the review dossier).
D — Hypeddit per campaign: visits, clicks and conversion were already the page's rings, so
only the new fact enters, under each ring — the Meta spend within 14 days of the release.
A second chart would have repeated the rings (R299).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.dashboard.utils import meta_impact

_DAYS = pd.date_range("2024-01-01", periods=120, freq="D")


def test_the_curve_is_indexed_on_the_28_days_before_each_wave():
    streams = pd.Series(50.0, index=_DAYS)
    streams.loc["2024-03-01":"2024-03-10"] = 150.0
    es = meta_impact.event_study(streams, [("A", dt.date(2024, 3, 1))])
    at = es.set_index("offset")["index"]
    assert at[-1] == 100.0 and at[0] == 300.0 and at[10] == 100.0


def test_the_curve_follows_the_days_whatever_order_the_query_returned():
    """`GROUP BY day` without ORDER BY: the first render in the app drew a zig-zag."""
    streams = pd.Series(range(120), index=_DAYS, dtype=float) + 50
    shuffled = streams.sample(frac=1.0, random_state=3)
    es = meta_impact.event_study(shuffled, [("A", dt.date(2024, 3, 1))])
    assert es["offset"].is_monotonic_increasing


def test_a_wave_with_almost_no_streams_before_it_is_left_out():
    """The first wave of artist 1 began before its first release: « indice 1 332 800 »."""
    streams = pd.Series(0.2, index=_DAYS)
    streams.loc["2024-03-01":] = 300.0
    assert meta_impact.event_study(streams, [("A", dt.date(2024, 3, 1))]).empty


def test_the_ads_around_a_release_are_the_14_days_on_each_side():
    spend = pd.DataFrame({"day": ["2024-03-01", "2024-03-15", "2024-03-29", "2024-03-30"],
                          "spend": [10.0, 20.0, 40.0, 80.0]})
    assert meta_impact.spend_around(spend, dt.date(2024, 3, 15)) == 70.0   # 01 → 29 inclusive
    assert meta_impact.spend_around(spend.iloc[0:0], dt.date(2024, 3, 15)) == 0.0


def test_the_ring_names_the_ads_only_when_they_are_known():
    from src.dashboard.views.hypeddit import ring_label
    with_ads = ring_label("Kimono", 3600, 580, 294.0)
    assert "294" in with_ads and "±14" in with_ads
    assert "±14" not in ring_label("Kimono", 3600, 580)
    assert "±14" not in ring_label("Kimono", 3600, 580, float("nan"))
