"""R349 — on « Mes sorties, à âge égal », a release linked by match_key receives its Meta
spend, and that spend is drawn as a CURVE.

Type: Test
Uses: src/dashboard/views/spotify_s4a_combined.py (release_spend, spend_curve,
      meta_spend_traces, _release_overlays)
Depends on: pandas, plotly — no database (pure frames and a fake `fetch_df`)
Persists in: nothing

Owner's screen review, 2026-10-04: the Meta €/day panel read as a cloud of points, and
the Meta series was absent for « Qui a bu le crachoir du saloon ? ». Cause read in the
code: the campaign -> release join was `lower(r.title) = lower(m.track_name)`, and
`campaign_track_mapping.track_name` is written in the S4A file spelling (`_` for `?`,
`meta_mapping/_campaigns.py`), so it never equals the release title. The join now goes
through the confirmed `track_platform_link` row and its `match_key`.

Mutation record (2026-10-04):
  * `meta_spend_traces` back to `mode="markers"` -> red:
    test_the_meta_panel_is_a_curve.
  * `release_spend` resolving by `lower(title) == lower(track_name)` instead of the
    link's match_key -> red (the « _ » spelling never equals « ? »):
    test_a_release_linked_by_match_key_receives_its_spend,
    test_two_platform_titles_do_not_double_the_spend,
    test_the_spend_stops_at_the_compared_horizon, test_the_meta_panel_is_a_curve,
    test_the_overlays_hand_the_link_frames_to_the_pure_join.
  * the `drop_duplicates()` on the resolved (campaign, match_key) pairs removed -> red:
    test_two_platform_titles_do_not_double_the_spend.
  * `spend_curve` returning the sparse frame unchanged -> red:
    test_a_pause_between_two_spending_days_is_drawn_at_zero.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.dashboard.views import spotify_s4a_combined as page

_REL = dt.date(2025, 3, 1)


def _frames(spend_days=((0, 10.0), (1, 5.0))):
    spend = pd.DataFrame({
        "artist_id": [1] * len(spend_days),
        "campaign_name": ["Crachoir - Conversions"] * len(spend_days),
        "day": [_REL + dt.timedelta(days=d) for d, _ in spend_days],
        "spend": [s for _, s in spend_days],
    })
    # The S4A file spelling: « _ » where the real title has « ? ».
    mapping = pd.DataFrame({"artist_id": [1], "campaign_name": ["Crachoir - Conversions"],
                            "track_name": ["Qui a bu le crachoir du saloon _"]})
    links = pd.DataFrame({"artist_id": [1, 1], "match_key": ["crachoir", "crachoir"],
                          "platform_title": ["Qui a bu le crachoir du saloon _ ",
                                             "Qui a bu le crachoir du saloon ?"]})
    releases = pd.DataFrame({"artist_id": [1], "match_key": ["crachoir"],
                             "title": ["Qui a bu le crachoir du saloon ?"],
                             "release_date": [_REL]})
    return spend, mapping, links, releases


def test_a_release_linked_by_match_key_receives_its_spend():
    out = page.release_spend(*_frames(), horizon=30)
    assert list(out["title"].unique()) == ["Qui a bu le crachoir du saloon ?"]
    assert out["spend"].sum() == 15.0
    assert list(out["day_index"]) == [0, 1]


def test_an_unlinked_campaign_name_draws_nothing():
    spend, mapping, links, releases = _frames()
    out = page.release_spend(spend, mapping, links.iloc[0:0], releases, horizon=30)
    assert out.empty


def test_two_platform_titles_do_not_double_the_spend():
    spend, mapping, links, releases = _frames()
    links = pd.concat([links, links.assign(platform_title="Qui a bu le crachoir du saloon _")],
                      ignore_index=True)
    assert page.release_spend(spend, mapping, links, releases, horizon=30)["spend"].sum() == 15.0


def test_the_spend_stops_at_the_compared_horizon():
    out = page.release_spend(*_frames(((-1, 3.0), (0, 10.0), (5, 7.0))), horizon=5)
    assert list(out["day_index"]) == [0], "before release and past the horizon are cut"


def test_another_tenants_link_does_not_resolve():
    spend, mapping, links, releases = _frames()
    out = page.release_spend(spend, mapping, links.assign(artist_id=2), releases, horizon=30)
    assert out.empty


def test_a_pause_between_two_spending_days_is_drawn_at_zero():
    meta = pd.DataFrame({"title": ["A", "A"], "day_index": [0, 3], "spend": [4.0, 6.0]})
    dense = page.spend_curve(meta)
    assert list(dense["day_index"]) == [0, 1, 2, 3]
    assert list(dense["spend"]) == [4.0, 0.0, 0.0, 6.0]


def test_the_meta_panel_is_a_curve():
    meta = page.release_spend(*_frames(), horizon=30)
    traces = page.meta_spend_traces(meta, {})
    assert traces and all(tr.mode == "lines" for tr in traces)


class _FakeDb:
    """Answers each overlay read by the table it names — no Postgres."""

    def __init__(self, frames: dict):
        self.frames = frames

    def fetch_df(self, sql, params):
        for table, frame in self.frames.items():
            if f"FROM {table}" in sql and "v_apple_song_daily" not in sql:
                return frame
        return pd.DataFrame()


def test_the_overlays_hand_the_link_frames_to_the_pure_join():
    spend, mapping, links, releases = _frames()
    db = _FakeDb({"v_meta_daily": spend, "campaign_track_mapping": mapping,
                  "track_platform_link": links, "track_release_reference": releases})
    meta, shazam = page._release_overlays(db, ["crachoir"], 30, "", ())
    assert meta["spend"].sum() == 15.0
    assert shazam.empty
