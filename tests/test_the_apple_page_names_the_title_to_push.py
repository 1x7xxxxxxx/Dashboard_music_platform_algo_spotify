"""R518 (X7 II) — Apple : « Le rythme d'un titre » replaced by « Shazams pour 1 000 écoutes ».

Type: Guard
Uses: src.dashboard.views.apple_music (shazams_per_thousand, _render_shazam_rate), ast
Depends on: nothing (pure function + a captured figure)
Persists in: nothing

Owner, 2026-10-11 : two bars per reading for ONE title led to no decision. A Shazam is
someone searching the title after hearing it ; the title with the most Shazams per
1 000 plays is the one to push in an ad. What must hold:
1. the rate is Shazams / plays × 1 000, ranked highest first ;
2. a title under MIN_PLAYS is not ranked (53 Shazams on 30 plays is noise, not 1 767) ;
3. the figure puts the best title on TOP and names it in the title ;
4. the old one-title pace chart is gone from the page.

Mutation record (2026-10-11): seen red with `* 1000` removed, the `min_plays` filter
removed, `ascending=False` → True, and the `iloc[::-1]` reversal removed.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from src.dashboard.views import apple_music as page

_DF = pd.DataFrame({
    "song_name": ["Cherché", "Écouté", "Trop jeune", "Moyen"],
    "plays": [309, 438, 30, 477],
    "shazam_count": [637, 2, 53, "475"],
})


def test_the_rate_is_per_thousand_plays_and_ranked() -> None:
    r = page.shazams_per_thousand(_DF)
    assert r["song_name"].tolist() == ["Cherché", "Moyen", "Écouté"]
    assert r["rate"].tolist() == [2061.0, 996.0, 5.0]


def test_a_title_under_the_floor_is_not_ranked() -> None:
    assert "Trop jeune" not in page.shazams_per_thousand(_DF)["song_name"].tolist()
    assert page.MIN_PLAYS >= 50


def test_the_figure_puts_the_title_to_push_on_top(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(page.charts, "plotly_chart", lambda fig, **_: seen.append(fig))
    page._render_shazam_rate(_DF)
    (fig,) = seen
    assert list(fig.data[0].y)[-1] == "Cherché", "plotly draws bottom-up : the best is last"
    assert "Cherché" in fig.layout.title.text


def test_the_one_title_pace_chart_is_gone() -> None:
    tree = ast.parse(Path(page.__file__).read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not names & {"_render_song_series", "rate_per_30_days", "pace_verdict"}
    show = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "show")
    called = {getattr(c.func, "id", None) for c in ast.walk(show) if isinstance(c, ast.Call)}
    assert "_render_shazam_rate" in called
