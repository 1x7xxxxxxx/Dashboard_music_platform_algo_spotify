"""Every euro is on the Trésorerie page — ADR-033 decision 1 (R553, owner Y1).

Type: Guard
Uses: src/dashboard/views/*.py (AST), src.dashboard.routes
Depends on: nothing
Persists in: nothing

« Consolider tous les graphiques de revenue (même avec source Meta) dans la vue revenue »:
the break-even was drawn by three pages (the cross view, the algo page's « Budget & ROI »
and its « Mon argent »). One chart, one caller.

Mutations, 2026-10-13:
  - `render_break_even(db, artist_id)` put back in `meta_ads_overview._render_revenue` → RED;
  - `render_artist_money` call dropped from `imusician._render_money` → RED;
  - `render_ltv` rendered by `imusician` → RED (the operator's number);
  - `revenue_forecast` routed back to `views.trigger_algo` → RED.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.routes import PAGE_ALIASES, ROUTES

_VIEWS = Path("src/dashboard/views")
# The money renderers, and the ONE module allowed to call each.
_OWNER = {
    "render_break_even": "imusician.py",
    "render_artist_money": "imusician.py",
    "breakeven_figure": "imusician.py",
    "render_ltv": "admin.py",
}


def _callers(name: str) -> set[str]:
    found = set()
    for path in _VIEWS.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if callee == name:
                    found.add(str(path.relative_to(_VIEWS)))
    return found


def test_each_money_renderer_has_one_caller() -> None:
    for name, owner in _OWNER.items():
        assert _callers(name) == {owner}, f"{name} is called from {_callers(name)}, not {owner}"


def test_the_old_money_key_lands_on_the_treasury() -> None:
    assert ROUTES["revenue_forecast"] == "views.imusician"
    assert PAGE_ALIASES["revenue_forecast"] == "imusician"


def test_the_ltv_stays_behind_the_admin_check() -> None:
    tree = ast.parse((_VIEWS / "revenue_forecast.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == "render_ltv")
    guard = next(n for n in fn.body if isinstance(n, ast.If))
    assert "is_admin" in ast.unparse(guard.test), "the LTV renders without the admin check"
