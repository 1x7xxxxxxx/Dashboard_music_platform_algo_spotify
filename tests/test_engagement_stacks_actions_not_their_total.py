"""R271 (owner note L242) — the engagement panels stack the five specific actions, never
Meta's `page_interactions` aggregate that contains them.

Type: Test
Uses: src/dashboard/views/meta_breakdowns.py (_ENG_STACK, _render_engagement)

Measured 2026-09-28: `page_interactions` 284 847 against 27 268 for the specific actions —
stacked, it counted each action twice and crushed them; seven series on a five-colour
palette drew off-theme colours, and a 10 px margin cut the placement labels.

Mutation record (2026-09-28) : `page_interactions` put back in `_ENG_STACK` → red ;
`color_discrete_sequence` removed → red.
"""
import ast
from pathlib import Path

from src.dashboard.utils.platform_colors import DISTINCT
from src.dashboard.views import meta_breakdowns as mb



def test_the_aggregate_is_not_stacked_with_what_it_contains():
    assert "page_interactions" not in mb._ENG_STACK
    assert len(mb._ENG_STACK) <= len(DISTINCT), "one palette colour per stacked series"


def test_the_engagement_is_a_grid_not_a_stacked_bar():
    # R558 (fiche 33): the stacked bar hid 39 comments beside 12 248 reactions.
    src = Path(mb.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_render_engagement")
    calls = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "go.Heatmap" in calls and "engagement_grid.column_shade" in ast.unparse(fn), calls
    assert not {"px.bar", "go.Bar"} & calls, calls
