"""
Guard — une vue n'ouvre pas sur un mur de graphiques.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/views/**, src/dashboard/utils/ui.py
Persists in: nothing

Error class: too-many-charts-competing-for-one-decision.

Remonté par un artiste en test le 2026-08-12 : « réduire le nombre de graphs qui
permettent de prendre décision ». Le correctif — `ui.secondary_analyses()`, un dépliant
qui applique « une décision par écran » — a été écrit **le jour même**, avec la remarque
citée dans son propre commentaire de module.

Onze jours plus tard il était appliqué sur quatre sites, et sur **aucune** des cinq vues
les plus denses :

    Road to Algo  15 graphiques + jusqu'à 17 jauges ≈ 35 figures
    Data Wrapped   9
    Créatives      8
    Meta Ads       8
    Prévisions     6

Le correctif existait, le diagnostic était juste, et la distance entre les deux n'était
mesurée nulle part. Ce garde la mesure.

Ce qu'il compte : les graphiques rendus **au premier écran**, c'est-à-dire hors d'un
`with secondary_analyses(...)` et hors d'un `st.expander(...)`. Rien n'interdit d'en avoir
beaucoup — il faut seulement qu'ils ne soient pas tous dépliés d'emblée.
"""

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"
_RENDERERS = {"plotly_chart", "altair_chart", "line_chart", "bar_chart",
              "area_chart", "pyplot"}
# Plafond du PREMIER ÉCRAN. Few (*Information Dashboard Design*) : un tableau de bord
# tient dans un coup d'œil. Cinq laisse de la marge tout en interdisant le mur.
_MAX_FIRST_SCREEN = 5


def _view_files() -> list[str]:
    out = []
    for p in sorted(_VIEWS.rglob("*.py")):
        if "__pycache__" in str(p) or p.name.startswith("__"):
            continue
        out.append(str(p.relative_to(_ROOT)))
    return out


def _collapsed_lines(tree: ast.Module) -> set[int]:
    """Lignes vivant dans un dépliant — `secondary_analyses(...)` ou `st.expander(...)`."""
    covered = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        names = {
            (getattr(i.context_expr.func, "id", "")
             or getattr(i.context_expr.func, "attr", ""))
            for i in node.items if isinstance(i.context_expr, ast.Call)
        }
        if names & {"secondary_analyses", "expander"}:
            for stmt in node.body:
                covered |= set(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
    return covered


def _first_screen_charts(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    collapsed = _collapsed_lines(tree)
    return sorted(
        n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "attr", "") in _RENDERERS
        and n.lineno not in collapsed
    )


def test_the_tool_still_exists():
    ui = (_ROOT / "src" / "dashboard" / "utils" / "ui.py").read_text(encoding="utf-8")
    assert "def secondary_analyses" in ui, (
        "`secondary_analyses` a disparu — c'est le seul motif de dépliage que ce garde "
        "reconnaît, et il a été écrit pour cette remarque précise."
    )


@pytest.mark.parametrize("rel", _view_files())
def test_a_view_does_not_open_on_a_wall_of_charts(rel: str):
    lines = _first_screen_charts(_ROOT / rel)
    assert len(lines) <= _MAX_FIRST_SCREEN, (
        f"{rel} rend {len(lines)} graphiques au PREMIER ÉCRAN (lignes {lines[:8]}…). "
        f"Plafond : {_MAX_FIRST_SCREEN}. Replie les graphiques qui RAFFINENT une "
        f"décision sans la faire :\n"
        f"    with secondary_analyses():\n"
        f"        st.plotly_chart(fig_detail, width=\"stretch\")\n"
        f"Rien n'est supprimé — tout reste à un clic."
    )
