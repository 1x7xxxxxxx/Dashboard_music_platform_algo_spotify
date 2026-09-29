"""A base that does not answer halts the page with a message — it never crashes it.

Type: Sub
Uses: src/dashboard/utils/__init__.py (view_session, require_db), src/dashboard/views/ (AST)
Depends on: nothing — mocks for Streamlit, the views' source read as syntax trees

R332 (2026-09-29): with the local Postgres down after a restart, the admin « santé » page
crashed on `'NoneType' object has no attribute 'close'`. `get_db_connection()` returns
None by contract; `view_session()` (16 views and 7 fragments inherit it) and five views
handed that None to their body. The sweep found them by the PROPERTY « can the db this
code receives be None? », not by the spelling `db = get_db_connection()` — which is why
the second test reads the syntax tree of every call, not a line pattern.

Mutation record (2026-09-29): seen red with `require_db` removed from `view_session()`,
and with `require_db(...)` unwrapped in `views/billing.py`.
"""
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.dashboard.utils import view_session

VIEWS = Path(__file__).resolve().parents[1] / "src/dashboard/views"


class _Stop(Exception):
    """Stand-in for streamlit's st.stop() halt."""


def test_view_session_halts_on_an_unreachable_base_before_the_body() -> None:
    st = MagicMock()
    st.stop.side_effect = _Stop
    entered = False
    with patch("src.dashboard.utils.get_db_connection", return_value=None), \
         patch("streamlit.error", st.error), patch("streamlit.stop", st.stop), \
         patch("src.dashboard.auth.get_artist_id", return_value=7), \
         patch("src.dashboard.auth.is_admin", return_value=False):
        try:
            with view_session():
                entered = True
        except _Stop:
            pass
    assert not entered, "the view's body ran with db=None"
    st.error.assert_called_once()
    assert "injoignable" in st.error.call_args[0][0].lower() or \
        "unreachable" in st.error.call_args[0][0].lower()


def _unguarded(tree: ast.AST) -> list[int]:
    """Lines where `get_db_connection()` reaches code without require_db or a None test."""
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    bad = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "get_db_connection"):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.Call) and getattr(parent.func, "id", None) == "require_db":
            continue
        fn = parent
        while fn is not None and not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn = parents.get(fn)
        name = parent.targets[0].id if isinstance(parent, ast.Assign) and \
            isinstance(parent.targets[0], ast.Name) else None
        tested = name and fn and any(
            isinstance(c, ast.Compare) and isinstance(c.left, ast.Name) and c.left.id == name
            and any(isinstance(op, (ast.Is, ast.IsNot)) for op in c.ops)
            or isinstance(c, ast.UnaryOp) and isinstance(c.op, ast.Not)
            and isinstance(c.operand, ast.Name) and c.operand.id == name
            for c in ast.walk(fn))
        if not tested:
            bad.append(node.lineno)
    return bad


def test_every_view_connection_is_checked_for_none() -> None:
    found = {str(p.relative_to(VIEWS)): lines for p in sorted(VIEWS.rglob("*.py"))
             if (lines := _unguarded(ast.parse(p.read_text(encoding="utf-8"))))}
    assert not found, (
        "a view uses get_db_connection() without require_db() nor a None branch — "
        f"with the base down it crashes instead of saying so: {found}")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    raw = "def show():\n    db = get_db_connection()\n    db.close()\n"
    guarded = "def show():\n    db = get_db_connection()\n    if db is None:\n        return\n"
    wrapped = "def show():\n    db = require_db(get_db_connection())\n    db.close()\n"
    assert _unguarded(ast.parse(raw)) == [2]
    assert _unguarded(ast.parse(guarded)) == [] and _unguarded(ast.parse(wrapped)) == []
