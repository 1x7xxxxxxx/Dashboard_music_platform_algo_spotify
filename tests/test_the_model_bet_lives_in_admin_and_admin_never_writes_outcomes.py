"""R442 — the model's bet moved to the admin ML page; the outcome grids stayed with the artist.

Type: Guard
Uses: src/dashboard/views/ml_performance.py, src/dashboard/views/trigger_algo/_outcome_entry.py
Depends on: nothing (AST only)
Persists in: nothing

The owner asked (2026-10-07) to move « Le pari du modèle… » through « Enregistrer la
période (algos) » to the admin view. Only the read-only chart moved: the grids write
`s4a_song_algo_outcomes`, which become training labels, and the admin page has no
tenant — an entry there would be written under the admin's identity.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ADMIN = Path("src/dashboard/views/ml_performance.py")
_ENTRY = Path("src/dashboard/views/trigger_algo/_outcome_entry.py")


def _called(path: Path, func: str | None = None) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if func:
        tree = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == func)
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            names.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    return names


def test_the_admin_ml_page_renders_the_bet() -> None:
    assert "render_prediction_vs_reality" in _called(_ADMIN, "_show_bet_tab")
    assert "_show_bet_tab" in _called(_ADMIN, "show")


def test_the_bet_tenant_is_picked_not_read_from_the_session() -> None:
    calls = _called(_ADMIN, "_show_bet_tab")
    assert "selectbox" in calls, "the admin bet has no explicit artist picker"
    assert not calls & {"get_artist_id", "get"}, "the admin bet reads its tenant from the session"


def test_the_admin_ml_page_never_writes_outcomes() -> None:
    calls = _called(_ADMIN)
    assert not calls & {"upsert_many", "render_outcome_grid", "render_outcome_custom_grid",
                        "render_outcomes", "execute"}, calls & {"upsert_many", "execute"}


def test_the_artist_entry_no_longer_draws_the_bet() -> None:
    calls = _called(_ENTRY, "render_outcomes")
    assert "render_prediction_vs_reality" not in calls
    assert {"render_outcome_grid", "render_outcome_custom_grid"} <= calls


def test_the_page_blurb_no_longer_promises_the_model_bet() -> None:
    """R512 (X4) — the section blurb still announced « le pari du modèle » after it moved."""
    from src.dashboard.views.trigger_algo._sections import PAGE_SECTIONS
    from src.dashboard.utils.i18n_catalog.trigger_algo import EN as STRINGS
    blurbs = [s[4] for s in PAGE_SECTIONS] + [STRINGS[s[3]] for s in PAGE_SECTIONS if s[3] in STRINGS]
    assert not [b for b in blurbs if "pari du modèle" in b or "model's bet" in b], blurbs
