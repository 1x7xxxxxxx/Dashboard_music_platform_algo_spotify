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
    ax = figures[SHAP_OVERVIEW].axes[0]   # R487 : « Ta track » is the second panel
    labels = " ".join(t.get_text() for t in ax.texts)
    assert all(p in labels for p in ("Discover Weekly", "Release Radar", "Radio"))
    assert any(p.get_width() < 0 for p in ax.patches), "a criterion that slows down is drawn left"
    # R480 (W3) : no « Exemple — données fictives » drawn into the image any more.
    assert "fictives" not in " ".join(t.get_text() for t in figures[SHAP_OVERVIEW].texts + ax.texts)


def test_the_shap_example_places_our_track_on_each_criterion(monkeypatch) -> None:
    """R487 (W10) : « ajouter NOTRE track, sa position sur chaque critère avec un score et
    la dépense Meta associée » — a second panel on the same rows."""
    spec = importlib.util.spec_from_file_location("_r487_charts", SCRIPT)
    charts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(charts)
    figures = {}
    monkeypatch.setattr(charts, "_save", lambda fig, name: figures.setdefault(name, fig))
    charts.shap_overview()
    shap, mine = figures[SHAP_OVERVIEW].axes
    figures[SHAP_OVERVIEW].canvas.draw()   # tick labels are only formatted at draw time
    assert mine.get_title(loc="left") == "Ta track"
    rows = [t.get_text() for t in shap.get_yticklabels()]
    assert len(rows) == 6 and "" not in rows, f"the criteria lost their names: {rows}"
    notes = [t.get_text() for t in mine.texts]
    assert len(notes) == len(rows) and all("/100" in n for n in notes)
    assert any("€ Meta" in n for n in notes), "the Meta spend is not drawn"


_CTA_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import src.dashboard.views.algo_preview as v
import streamlit as st
_lock = v.est_verrouille
_goto = v.goto
v.est_verrouille = lambda key, plan=None: {locked}
v.goto = lambda key: st.session_state.__setitem__("went", key)
try:
    v.show()
finally:
    v.est_verrouille = _lock
    v.goto = _goto
"""


def _cta(locked: bool):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(_CTA_SCRIPT.format(root=str(ROOT), locked=locked))
    at.run(timeout=60)
    assert not at.exception, at.exception
    (button,) = at.button
    label = button.label
    button.click().run(timeout=60)
    return label, at.session_state["went"]


def test_a_free_artist_is_sent_to_billing() -> None:
    """R487 (W10) : « bouton vers Facturation pour passer premium si on ne l'est pas »."""
    label, went = _cta(locked=True)
    assert went == "billing" and "Premium" in label and "🔒" not in label


def test_a_premium_artist_opens_road_to_algo() -> None:
    label, went = _cta(locked=False)
    assert went == "trigger_algo" and "Road to Algo" in label


def test_no_help_text_below_the_figures() -> None:
    """R487 (W10) : « retirer le texte de droite » — the caption under the figures."""
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    show = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "show")
    assert not {"caption", "markdown", "info", "write"} & _calls(show)
