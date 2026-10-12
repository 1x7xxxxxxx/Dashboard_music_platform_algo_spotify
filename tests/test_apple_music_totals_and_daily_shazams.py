"""Apple Music — the Total row of the top 10 (R534); the page is that figure only (R546).

Type: Test
Uses: src.dashboard.views.apple_music (_top10_figure, show), ast

Owner, 2026-10-12: « Total en première ligne avec un libellé, puis les titres » ; and a
daily Shazam chart where several days without an import read as an AVERAGE, never as
one day carrying them all. That daily chart and « le titre à pousser » were removed
on 2026-10-12 (R546, owner: « tu me supprimes les deux »).

Mutation record — 2026-10-12: with `_render_shazam_rate(df_all)` put back in `show()`,
`test_the_page_is_the_top10_and_its_shazams_only` is red naming it.
"""
from __future__ import annotations

import ast
import inspect

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


def test_the_page_is_the_top10_and_its_shazams_only():
    """R546 — `show()` draws one figure: the top 10 with its Shazams panel."""
    tree = ast.parse(inspect.getsource(am.show))
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "_top10_figure" in called, "the top 10 is gone from the page"
    removed = {c for c in called if "shazam_rate" in c or "shazam_gains" in c}
    assert not removed, f"R546: removed by the owner, drawn again: {sorted(removed)}"
    assert sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call)
               and getattr(n.func, "attr", "") == "plotly_chart") == 1, (
        "R546: the Apple page has ONE figure — the top 10 and its Shazams")
