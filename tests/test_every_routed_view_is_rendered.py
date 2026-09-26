"""Every view the route table can open is rendered by the smoke harness.

Type: Sub
Uses: src/dashboard/app.py (AST of the route table), tests/render_harness.py (VIEWS,
      EMPTY_TENANT_VIEWS)
Depends on: nothing (reads files, renders nothing)
Persists in: nothing

2026-09-26. `algo_preview` was added by the three steps CLAUDE.md documents for a new view
(module, menu entry, route) and nothing rendered it: the harness lists its views by hand.
Two older routes had the same gap — `platform_status` (off the menu since 2026-09-05, still
routed) and `privacy` (the public page). A view that no test renders reaches production on
its first click, which is exactly what the render harness exists to prevent.

The route table is read as an AST: a `from views.<x> import show` anywhere in `app.py`
names a view the app can open. A comment or a string naming a view cannot satisfy it.
"""
from __future__ import annotations

import ast
from pathlib import Path

from tests.render_harness import EMPTY_TENANT_VIEWS, VIEWS

_APP = Path(__file__).resolve().parent.parent / "src" / "dashboard" / "app.py"


def _routed_views(tree: ast.AST) -> set[str]:
    """Modules the route table imports `show` from — `views.<x>`, first segment only."""
    return {n.module.split(".")[1] for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom) and n.module
            and n.module.startswith("views.") and any(a.name == "show" for a in n.names)}


def _unrendered(tree: ast.AST, rendered: set[str]) -> set[str]:
    return _routed_views(tree) - rendered


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """A route to a view absent from the harness is seen; a comment naming it is not a route."""
    defect = ast.parse('if page == "x":\n    from views.newpage import show; show()\n')
    assert _unrendered(defect, {"home"}) == {"newpage"}, "an unrendered route was missed"
    aliased = ast.parse("from views.privacy import show as show_privacy\n")
    assert _unrendered(aliased, set()) == {"privacy"}, "an aliased show was missed"
    prose = ast.parse('# from views.ghost import show\nX = "from views.ghost import show"\n')
    assert _unrendered(prose, set()) == set(), "prose about a route counted as a route"
    assert not _unrendered(defect, {"newpage"}), "a rendered view was reported"


def test_every_routed_view_is_rendered() -> None:
    missing = _unrendered(ast.parse(_APP.read_text(encoding="utf-8")),
                          set(VIEWS) | set(EMPTY_TENANT_VIEWS))
    assert not missing, (
        f"routed in app.py but rendered by no test: {sorted(missing)} — add them to "
        "VIEWS (admin render) in tests/render_harness.py, and to EMPTY_TENANT_VIEWS if an "
        "artist reaches them")
