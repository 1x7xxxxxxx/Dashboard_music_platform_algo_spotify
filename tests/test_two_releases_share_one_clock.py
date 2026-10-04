"""Two releases give two Shazam series aligned on J0 (R351).

Type: Test
Uses: pandas, pytest, streamlit.testing.v1.AppTest (render half only)
Depends on: src/dashboard/utils/apple_launches.py, src/dashboard/views/apple_music.py,
            a provisioned Postgres for the render half (skipped otherwise)
Persists in: nothing

The owner's request (screen review, 2026-10-04): on the Apple Music page, the evolution of
Shazams across TWO campaigns — the latest release by default, a second one chosen — on the
same clock so they compare. « Same clock » is the property: day 0 of each series is ITS
release day, whatever the calendar year. And the grain is the trap: Apple readings are
CUMULATIVE snapshots, so the value is the lifetime count since release (never a gain divided
by days), and an export covering only a later period is not « since release ».

Mutation record (2026-10-04):
  - `offset` computed as `(d - min(all j0)).days` instead of `(d - launch.j0).days`
    (alignment dropped, one shared calendar origin) → RED
    `test_two_launches_give_two_series_aligned_on_j0` and
    `test_the_newer_release_is_not_shifted_by_the_older_one`.
  - the period filter `s <= launch.j0` turned into `True` (keep every export) → RED
    `test_an_export_that_starts_after_release_is_not_since_release`.
  - the `mine["day"] >= launch.j0` mask removed → RED
    `test_a_reading_before_release_is_dropped`.
  - `reverse=True` removed from `release_launches` (oldest first) → RED
    `test_the_latest_release_comes_first`.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.dashboard.utils.apple_launches import Launch, align_on_j0, release_launches

D = dt.date


def _readings(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["song_name", "day", "shazam_count", "period_start"])


def test_two_launches_give_two_series_aligned_on_j0() -> None:
    old, new = Launch("Old", D(2024, 1, 10)), Launch("New", D(2025, 6, 1))
    readings = _readings([
        ("Old", D(2024, 1, 20), 5, None), ("Old", D(2024, 2, 9), 12, None),
        ("New", D(2025, 6, 11), 30, None), ("New", D(2025, 7, 1), 70, None),
    ])
    got = align_on_j0(readings, [new, old])
    assert list(dict.fromkeys(got["song"])) == ["New", "Old"], "one series per launch, in order"
    for song, offsets, values in (("New", [0, 10, 30], [0, 30, 70]),
                                  ("Old", [0, 10, 30], [0, 5, 12])):
        s = got[got["song"] == song]
        assert s["offset"].tolist() == offsets, f"{song} is not on the J0 clock"
        assert s["shazams"].tolist() == values
        assert s["measured"].tolist() == [False, True, True], "J0 anchor is not a measure"


def test_the_newer_release_is_not_shifted_by_the_older_one() -> None:
    a, b = Launch("A", D(2023, 3, 1)), Launch("B", D(2026, 3, 1))
    got = align_on_j0(_readings([("A", D(2023, 3, 8), 1, None),
                                 ("B", D(2026, 3, 8), 2, None)]), [b, a])
    assert got.loc[got["measured"], "offset"].tolist() == [7, 7]


def test_an_export_that_starts_after_release_is_not_since_release() -> None:
    lc = Launch("T", D(2024, 1, 1))
    got = align_on_j0(_readings([
        ("T", D(2025, 12, 31), 40, D(2025, 1, 1)),   # « 2025 only »: understates the title
        ("T", D(2026, 1, 31), 300, None),             # « depuis le début »: qualifies
        ("T", D(2026, 2, 28), 310, D(2023, 6, 1)),    # period starts before J0: qualifies
    ]), [lc])
    assert got.loc[got["measured"], "shazams"].tolist() == [300, 310]


def test_a_reading_before_release_is_dropped() -> None:
    lc = Launch("T", D(2024, 5, 1))
    got = align_on_j0(_readings([("T", D(2024, 4, 1), 3, None),
                                 ("T", D(2024, 5, 3), 4, None)]), [lc])
    assert got["offset"].min() == 0
    assert got.loc[got["measured"], "offset"].tolist() == [2]


def test_a_reading_on_j0_replaces_the_anchor() -> None:
    lc = Launch("T", D(2024, 5, 1))
    got = align_on_j0(_readings([("T", D(2024, 5, 1), 9, None)]), [lc])
    assert got[["offset", "shazams", "measured"]].values.tolist() == [[0, 9.0, True]]


def test_no_reading_still_answers_with_the_anchor_only() -> None:
    got = align_on_j0(pd.DataFrame(), [Launch("T", D(2024, 5, 1))])
    assert got["measured"].tolist() == [False]


def test_the_latest_release_comes_first() -> None:
    from src.utils.track_matching import normalize_track_title
    rel = {normalize_track_title("Old one"): D(2023, 1, 1),
           normalize_track_title("New one"): D(2025, 1, 1)}
    got = release_launches(["Old one", "Undated", "New one"], rel)
    assert [lc.song for lc in got] == ["New one", "Old one"]


# ── The render half: the page draws the J0 figure without an error ──────────────
from tests.db_gate import db_ready  # noqa: E402


@pytest.mark.skipif(not db_ready(), reason="render half needs the provisioned Postgres")
def test_the_apple_page_draws_two_releases_on_the_j0_clock() -> None:
    import json
    import os

    from streamlit.testing.v1 import AppTest

    from tests.render_harness import SCRIPT

    at = AppTest.from_string(SCRIPT.format(root=os.getcwd(), view="apple_music"))
    at.run(timeout=180)
    assert not at.exception, at.exception
    # The view wraps its body in `except Exception → st.error`: an error there is a crash.
    assert not [e.value for e in at.error], [e.value for e in at.error]
    j0 = []
    for el in at.get("plotly_chart"):
        spec = json.loads(el.proto.spec)
        title = ((spec.get("layout") or {}).get("xaxis") or {}).get("title") or {}
        if "J0" in str(title.get("text", "")):
            j0.append(spec)
    if not j0:
        pytest.skip("artist 1 has no dated release with a qualifying Apple reading here")
    traces = j0[0]["data"]
    assert 1 <= len(traces) <= 2
    for tr in traces:
        assert tr["x"][0] == 0, "a series does not start at J0"
        assert all(x >= 0 for x in tr["x"])
