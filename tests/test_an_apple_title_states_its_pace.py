"""R484 — the pace of one Apple title, per 30 days, and whether it speeds up.

Type: Guard
Uses: src.dashboard.views.apple_music (rate_per_30_days, pace_verdict, _render_song_series)
Depends on: nothing (pure functions + a captured figure)
Persists in: nothing

Owner, 2026-10-09 (W7 II) : « Écoutes et Shazam dans le temps — je ne comprends pas quelle
décision prendre → redesign ». Apple readings are 12 to 179 days apart: a raw gain of 35
over 179 days and of 8 over 12 days are not comparable, and the old chart drew them side
by side. The pace per 30 days is, and the figure title says whether the title speeds up.
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from src.dashboard.views import apple_music as page


def test_a_gain_is_a_pace_per_30_days():
    pace = page.rate_per_30_days(pd.Series([35, 8, 5]), pd.Series([175, 12, 0]))
    assert pace.tolist()[:2] == [6.0, 20.0]
    assert pd.isna(pace.iloc[2]), "a zero-day interval has no pace, not an infinite one"


def test_the_verdict_reads_the_last_two_paces():
    assert page.pace_verdict(pd.Series([10, 20])).startswith("↗")
    assert page.pace_verdict(pd.Series([20, 10])).startswith("↘")
    assert page.pace_verdict(pd.Series([20, 21])).startswith("→")
    assert page.pace_verdict(pd.Series([0, 6])).startswith("↗"), "a take-off says so"
    assert page.pace_verdict(pd.Series([7])) == "", "one pace is not a trend"


def test_the_figure_draws_paces_over_their_interval(monkeypatch):
    seen = []
    monkeypatch.setattr(page.charts, "plotly_chart", lambda fig, **_: seen.append(fig))
    df = pd.DataFrame({"day": pd.to_datetime(["2025-11-29", "2025-12-11", "2026-06-08"]),
                       "daily_plays": [None, 8, 35], "daily_shazams": [None, 0, 0],
                       "days_since_previous": [None, 12, 179]})
    page._render_song_series(df, "Titre", SimpleNamespace(label="Tout"))
    fig = seen[0]
    plays = fig.data[0]
    assert list(plays.y) == [20.0, 6.0], "the bars are raw gains, not paces"
    assert plays.width[1] > plays.width[0] * 10, "a bar does not span its interval"
    assert "ralentit" in fig.layout.title.text, fig.layout.title.text
