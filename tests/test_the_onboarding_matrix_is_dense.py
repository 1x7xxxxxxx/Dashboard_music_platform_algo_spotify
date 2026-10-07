"""« Où tu en es » draws the status matrix as ONE compact table (R439, 2026-10-07).

Owner, on the assistant page: « c'est un peu gros et j'aimerais qu'on puisse accéder
directement au bouton Connecter mes sources ». The per-row `st.columns` layout and its
34 px boxes pushed the primary button below the fold. The dense form keeps the same
rows and the same cells — only their size changes.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.utils import status_matrix as sm

REPO = Path(__file__).resolve().parents[1]


def _render(monkeypatch, rows):
    calls = []
    monkeypatch.setattr(sm.st, "markdown", lambda body, **kw: calls.append(body))
    monkeypatch.setattr(sm, "row_cells", lambda r, i, p: [
        ("green", "✅", "set"), ("green", "✅", "shape"),
        ("grey", "?", "responds"), ("red", "❌", "data")])
    sm._render_dense(rows, {}, {})
    return calls


def test_the_dense_matrix_is_one_table_with_small_boxes(monkeypatch):
    rows = [{"key": "spotify", "label": "Spotify", "status": "todo",
             "next_action": "Colle ton lien\nartiste"},
            {"key": "youtube", "label": "YouTube <b>", "status": "ok",
             "next_action": ""}]
    calls = _render(monkeypatch, rows)
    assert len(calls) == 1, "dense mode must draw ONE markdown block, not a row per platform"
    html = calls[0]
    assert html.count("<tr>") == 3  # header + two platforms
    assert "min-width:22px" in html and "min-width:34px" not in html
    assert "Colle ton lien<br>artiste" in html
    assert "YouTube &lt;b&gt;" in html, "labels are escaped"


def test_the_full_size_box_is_unchanged():
    assert "min-width:34px" in sm._box("green", "✅", "tip")
    assert "min-width:22px" in sm._box("green", "✅", "tip", small=True)


def test_the_assistant_asks_for_the_dense_matrix():
    tree = ast.parse((REPO / "src/dashboard/views/onboarding.py").read_text("utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "render_status_matrix"]
    assert calls and all(
        any(k.arg == "dense" and getattr(k.value, "value", None) is True
            for k in c.keywords) for c in calls)
