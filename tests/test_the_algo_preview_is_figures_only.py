"""R456 — the algo preview shows the welcome figures plus a SHAP example, and nothing below.

Type: Test
Uses: src/dashboard/views/algo_preview.py (AST), tools/dev/make_example_charts (shap_overview)
Depends on: matplotlib (Agg)

Owner, 2026-10-07 (voice comments C8, C10): « remets-moi les mêmes graphiques que la mise
en route, plus petits ; en dessous, tu me supprimes tout le texte » and « un aperçu SHAP
qui liste l'impact de chaque paramètre sur Discover Weekly, Radio et Release Radar, avec
des données factices et une toute petite phrase ».

So `show()` reads no database (the real-data text is gone, not moved), renders exactly
ALGO_PREVIEW, and the SHAP figure ranks fake parameters for the three playlists.

Mutation record (2026-10-08): a `view_session()` put back in show() → red; ALGO_PREVIEW
reduced to two figures → red; one playlist dropped from the SHAP maker → red.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from src.dashboard.utils.example_figures import ALGO_PREVIEW, PROMISES, SHAP_OVERVIEW

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "src" / "dashboard" / "views" / "algo_preview.py"
SCRIPT = ROOT / "tools" / "dev" / "make_example_charts.py"
DB_CALLS = {"view_session", "get_db_connection", "tenant_scope", "fetch_df", "fetch_query"}


def _calls(tree: ast.AST) -> set[str]:
    return {getattr(n.func, "id", None) or getattr(n.func, "attr", "")
            for n in ast.walk(tree) if isinstance(n, ast.Call)}


def test_the_preview_is_the_welcome_figures_then_shap() -> None:
    assert ALGO_PREVIEW == (*PROMISES, SHAP_OVERVIEW)


def test_the_preview_reads_no_database() -> None:
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    show = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "show")
    assert not _calls(show) & DB_CALLS, "the text below the figures is gone, so is its query"
    assert "render_example" in _calls(show)


def test_the_detector_sees_a_database_read() -> None:
    assert _calls(ast.parse("with view_session() as (db, a):\n    db.fetch_df('x')")) & DB_CALLS


def test_the_shap_example_ranks_the_three_playlists(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("_r456_charts", SCRIPT)
    charts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(charts)
    figures = {}
    monkeypatch.setattr(charts, "_save", lambda fig, name: figures.setdefault(name, fig))
    charts.shap_overview()
    (ax,) = figures[SHAP_OVERVIEW].axes
    labels = " ".join(t.get_text() for t in ax.texts)
    assert all(p in labels for p in ("Discover Weekly", "Release Radar", "Radio"))
    assert any(p.get_width() < 0 for p in ax.patches), "a criterion that slows down is drawn left"
    assert "Exemple" in " ".join(t.get_text() for t in figures[SHAP_OVERVIEW].texts + ax.texts)
