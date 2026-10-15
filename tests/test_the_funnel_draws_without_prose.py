"""R591 — the cross view's funnel is read on its figure: no tile, no definition caption.

Type: Test
Uses: src/dashboard/views/meta_x_spotify.py

Owner, 2026-10-15: « retirer la prose (du 31/08 … CPR, coût d'un clic sortant) et les
tuiles dépenses / écoutes sur N jours / coût par écoute / CPR moyen » — the funnel draws
every one of those numbers; the definitions go to the glossary (R592).
"""
import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src/dashboard/views/meta_x_spotify.py"


def _calls(tree: ast.AST) -> set[str]:
    return {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}


def _defs() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_the_page_has_no_tile():
    calls = _calls(ast.parse(_SRC.read_text(encoding="utf-8")))
    assert not {c for c in calls if c.endswith(".metric")}, calls


def test_the_funnel_sections_write_no_caption():
    d = _defs()
    for name in ("render_funnel", "_render_funnel", "_render_pair"):
        assert "st.caption" not in _calls(d[name]), name
    assert "_funnel_note" not in d and "_render_tiles" not in d
