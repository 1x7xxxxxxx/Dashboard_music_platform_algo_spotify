"""R483 — « Ce qui bouge en ce moment » shows only what moves, the PI as its own bars.

Type: Guard
Uses: src/dashboard/views/spotify_s4a_combined.py (_render_momentum)
Depends on: pandas, plotly — no database (`_df` and the chart sink are replaced)
Persists in: nothing

Owner, 2026-10-09 (W6) : « seulement les titres qui bougent » ; II « popularity index sur
28 jours illisible → barres à côté … avec légende pertinente » ; « axe popularité borné
dynamiquement au max des valeurs ».
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from src.dashboard.views import spotify_s4a_combined as page

SPANS = pd.DataFrame({
    "song": ["big old", "new one", "trickle"],
    "streams_total": [90_000, 2_000, 500],
    "first_streamed": pd.to_datetime(["2023-01-01", "2026-09-01", "2024-01-01"]),
    "last_measured": pd.to_datetime(["2026-10-01"] * 3),
})
RECENT = pd.DataFrame({"song": ["big old", "new one", "trickle"], "recent": [400, 1_200, 9]})
PI = pd.DataFrame({"song": ["big old", "new one"], "popularity": [12, 9]})


def _figure(monkeypatch) -> object:
    def fake_df(_db, sql: str, _params: tuple) -> pd.DataFrame:
        return RECENT.copy() if "v_s4a_song_measured_span" in sql else PI.copy()

    seen = []
    monkeypatch.setattr(page, "_df", fake_df)
    monkeypatch.setattr(page.charts, "plotly_chart", lambda fig, **_: seen.append(fig))
    page._render_momentum(None, SPANS, "", (), SimpleNamespace(is_all_history=True),
                          "new one")
    assert len(seen) == 1
    return seen[0]


def test_a_trickle_is_not_shown_as_moving(monkeypatch) -> None:
    """9 streams in 28 days is below the selector's bar: the chart drops it too."""
    fig = _figure(monkeypatch)
    for trace in fig.data:
        assert "trickle" not in list(trace.y), f"« {trace.name} » montre un titre immobile"


def test_the_popularity_index_is_its_own_bars_on_a_bounded_axis(monkeypatch) -> None:
    fig = _figure(monkeypatch)
    pi_bars = [tr for tr in fig.data if list(tr.x) and set(tr.x) <= {12, 9}]
    assert len(pi_bars) == 1, "l'indice de popularité n'a pas ses propres barres"
    axis = fig.layout[pi_bars[0].xaxis.replace("x", "xaxis")]
    assert axis.range[1] < 50, f"axe PI non borné au max observé : {axis.range}"
    recent_bar = next(tr for tr in fig.data if 1_200 in list(tr.x))
    assert all("PI" not in str(t) for t in recent_bar.text), (
        "le PI est encore un suffixe de l'étiquette des 28 jours")
