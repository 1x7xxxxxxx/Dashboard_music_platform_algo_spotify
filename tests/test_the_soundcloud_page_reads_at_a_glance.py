"""SoundCloud reads at a glance: totals in the figures, five counters side by side (R486).

Type: Guard
Uses: src.dashboard.views.soundcloud
Depends on: nothing (pure figure builders)
Persists in: nothing

Owner, 2026-10-09 (W9, revue/notes-vocales-2026-10-09.md) : « les totaux du haut se
retrouvent dans les graphiques (on gagne une ligne) » ; « plusieurs Pareto sur une
même ligne : écoutes, engagement, likes, reposts, commentaires par track » ;
« expliquer le taux d'engagement » ; « retirer tout le blabla ».
"""
from __future__ import annotations

import pathlib

import pandas as pd

from src.dashboard.views import soundcloud as sc


def _src() -> str:
    return pathlib.Path(sc.__file__).read_text(encoding="utf-8")


def _tracks() -> pd.DataFrame:
    return sc._with_engagement(pd.DataFrame({
        "track_id": ["a", "b", "c"], "title": ["Petit", "Gros", "Moyen"],
        "playback_count": [10, 1000, 100], "likes_count": [5, 50, 2],
        "reposts_count": [0, 10, 1], "comment_count": [1, 5, 0],
        "track_created_at": pd.to_datetime(["2026-01-01"] * 3)}))


_TOTALS = {"playback_count": 1110, "likes_count": 57, "reposts_count": 11,
           "comment_count": 6}


def test_five_panels_share_rows_ordered_by_plays():
    fig = sc.top_figure(_tracks(), _TOTALS)
    assert len(fig.data) == 5, [tr.name for tr in fig.data]
    # plotly stacks bottom-up : the last row drawn is the top one.
    assert list(fig.data[0].y) == ["Petit", "Moyen", "Gros"]
    assert all(list(tr.y) == list(fig.data[0].y) for tr in fig.data), "rows not shared"


def test_each_panel_title_carries_its_total():
    titles = [a.text for a in sc.top_figure(_tracks(), _TOTALS).layout.annotations]
    assert "1 110" in titles[0] or "1 110" in titles[0] or "1,110" in titles[0], titles
    assert "6.7 %" in titles[1], titles     # (57 + 11 + 6) / 1110 = 6.67
    assert titles[4].endswith("<b>6</b>"), titles


def test_the_engagement_rate_is_defined_on_the_figure():
    title = sc.top_figure(_tracks(), _TOTALS).layout.title.text
    assert "÷" in title and "likes" in title.lower(), title
    assert sc.engagement_rate(_TOTALS) == 100 * 74 / 1110
    assert sc.engagement_rate({"playback_count": 0}) is None


def test_the_totals_line_names_the_four_counters():
    line = sc.totals_line(_TOTALS)
    assert line.count("·") == 3 and "57" in line and "11" in line, line


def test_the_tiles_and_their_blabla_are_gone():
    _SRC = _src()
    assert "st.metric" not in _SRC and ".metric(" not in _SRC
    for key in ("soundcloud.likes_caption", "soundcloud.age_caption",
                "soundcloud.catalog_caption", "soundcloud.top_caption",
                "soundcloud.top_table"):
        assert key not in _SRC, key


def test_the_age_comparison_opens_on_every_title():
    assert "n=len(titles)" in _src()
