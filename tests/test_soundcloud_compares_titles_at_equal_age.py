"""SoundCloud: four counters on one row, titles compared at equal age with Spotify's drawing (R385).

Type: Guard
Uses: src.dashboard.views.soundcloud, src.dashboard.utils.age_aligned, tests/render_harness.py
Depends on: live Postgres with artist 1's SoundCloud readings for the render (skipped without)
Persists in: nothing

V42-V46 (owner's screen review, 2026-10-05): plays, likes, reposts and comments on ONE
line; a chart comparing the releases on these counters, the engagement rate explained;
« tout le catalogue » — pick titles, compare them cumulated at equal age, reusing the
Spotify « sorties à J égal » component: one function, two callers, not a copy.
"""
from __future__ import annotations

import ast
import os
import pathlib

import pandas as pd
import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_VIEWS = ("src/dashboard/views/soundcloud.py", "src/dashboard/views/spotify_s4a_combined.py")


def _daily(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["track_id", "day", "plays", "lisible", "lisible_flag"])


def test_readings_sit_at_the_title_age_and_skip_an_unreadable_day() -> None:
    from src.dashboard.views.soundcloud import age_aligned_readings

    chosen = pd.DataFrame({"track_id": ["b", "a"], "title": ["B", "A"],
                           "track_created_at": [pd.Timestamp("2026-01-01 18:00"),
                                                pd.Timestamp("2025-01-01")]})
    daily = _daily([("a", "2026-01-11", 10, True, True),
                    ("a", "2026-01-12", 0, False, True),       # failed collection
                    ("b", "2026-01-11", 5, True, True),
                    ("b", "2026-01-12", 6, True, True)])
    out = age_aligned_readings(daily, chosen, "plays", "lisible_flag")
    assert 0 not in out["value"].tolist(), "an unreadable reading was drawn"
    assert out["title"].tolist() == ["B", "B", "A"], "the order is not the picker's"
    assert out["age"].tolist() == [10, 11, 375], out
    assert out["age"].min() > 0, "a (0, 0) origin was invented"


def test_only_the_last_point_carries_its_value() -> None:
    from src.dashboard.utils.age_aligned import age_aligned_traces

    df = pd.DataFrame({"t": ["x", "x", "x"], "d": [0, 1, 2], "v": [1, 2, 3000]})
    (trace,) = age_aligned_traces(df, x="d", y="v", series="t", colour={})
    assert list(trace.text)[:-1] == ["", ""] and list(trace.text)[-1] == "3 000"


def _calls(path: str, name: str) -> int:
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    return sum(isinstance(n, ast.Call) and getattr(n.func, "id", None) == name
               for n in ast.walk(tree))


@pytest.mark.parametrize("path", _VIEWS)
def test_both_views_draw_through_the_one_function(path: str) -> None:
    assert _calls(path, "age_aligned_traces") == 1, (
        f"{path} does not draw its equal-age curves through age_aligned_traces")


def _metric_rows(node) -> list[int]:
    """For every horizontal block holding a metric: its number of columns."""
    out = []
    kids = list(getattr(node, "children", {}).values())
    cols = [k for k in kids if type(k).__name__ == "Column"]
    if cols and any(getattr(x, "type", "") == "metric" for c in cols for x in _walk(c)):
        out.append(len(cols))
    for k in kids:
        out += _metric_rows(k)
    return out


def _walk(node):
    for c in getattr(node, "children", {}).values():
        yield c
        yield from _walk(c)


def _has_readings() -> bool:
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        return bool(db.fetch_query(
            "SELECT 1 FROM v_soundcloud_track_daily WHERE artist_id = 1 AND lisible LIMIT 1"))
    finally:
        db.close()


@pytest.mark.skipif(not db_ready(), reason="renders the SoundCloud page against the live DB")
def test_the_page_puts_four_counters_on_one_row_and_compares_at_equal_age() -> None:
    if not _has_readings():
        pytest.skip("artist 1 has no SoundCloud reading — the page renders its empty state")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="soundcloud",
                                                  artist_id=1))
    at.run(timeout=120)
    assert not at.exception, at.exception

    assert len(at.metric) == 4, [m.label for m in at.metric]
    assert sorted(_metric_rows(at._tree)) == [4], (
        f"the four counters are not on one row of four: {_metric_rows(at._tree)}")

    heads = [s.value for s in at.subheader]
    assert heads and "compar" in heads[0], f"the comparison is not on top: {heads}"
    pickers = [m for m in at.multiselect if "Titres à comparer" in m.label]
    assert len(pickers) == 1, "the equal-age comparison has no title picker"
    assert len(pickers[0].value) == min(2, len(pickers[0].options))
    assert any("à âge égal" in h for h in heads), heads
