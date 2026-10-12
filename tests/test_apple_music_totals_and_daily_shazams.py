"""Apple Music — Total row, and Shazams gained per day from cumulative readings (R534).

Type: Test
Uses: src.dashboard.views.apple_music (_top10_figure, daily_shazam_gains)

Owner, 2026-10-12: « Total en première ligne avec un libellé, puis les titres » ; and a
daily Shazam chart where several days without an import read as an AVERAGE, never as
one day carrying them all.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.views import apple_music as am


def test_the_total_is_the_first_row_of_both_panels():
    top = pd.DataFrame({"song_name": ["A", "B"], "plays": [100, 300],
                        "shazam_count": [5, 9]})
    fig = am._top10_figure(top, "400", "14")
    order = list(fig.layout.yaxis.categoryarray)
    assert order[-1] == "Total", "plotly draws bottom-up: the Total must be LAST to be on top"
    texts = [tr.text[0] for tr in fig.data if tr.type == "scatter"]
    assert [s.strip() for s in texts] == ["<b>400</b>", "<b>14</b>"]


def _hist(rows):
    return pd.DataFrame(rows, columns=["song_name", "day", "shazam_count"])


def test_a_gap_is_spread_as_an_average_never_one_day():
    g = am.daily_shazam_gains(_hist([("A", "2026-10-01", 10), ("A", "2026-10-04", 40),
                                     ("A", "2026-10-05", 45)]))
    assert list(g["gain"]) == [10, 10, 10, 5]
    assert list(g["span"]) == [3, 3, 3, 1]
    assert g["gain"].sum() == 35, "the spread must keep the total gained"


def test_titles_add_up_and_a_drop_is_not_negative():
    g = am.daily_shazam_gains(_hist([("A", "2026-10-01", 10), ("A", "2026-10-02", 12),
                                     ("B", "2026-10-01", 50), ("B", "2026-10-02", 20)]))
    assert list(g["gain"]) == [2], "B went down (other export window): left out, not -30"


def test_a_single_reading_has_no_gain():
    assert am.daily_shazam_gains(_hist([("A", "2026-10-01", 10)])).empty
