"""R585 — the manual money entry is its own page, after Hypeddit; Trésorerie only reads.

Type: Guard
Uses: src/dashboard/utils/nav_sections.py, src/dashboard/routes.py,
      src/dashboard/views/{imusician,revenue_forecast,saisie_tresorerie}.py
Depends on: nothing (AST + constants)
Persists in: nothing

Owner, Trésorerie 2026-10-15: « la saisie manuelle dans une vue après Hypeddit, et deux
boutons dans la trésorerie ». Read through the AST: which function CALLS which.
"""
from __future__ import annotations

import ast
from pathlib import Path

_VIEWS = Path("src/dashboard/views")


def _calls(path: Path, func: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == func)
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            out.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    return out


def test_the_entry_page_sits_right_after_hypeddit_and_is_routed() -> None:
    from src.dashboard.routes import ROUTES
    from src.dashboard.utils.nav_sections import NAV_SECTIONS

    keys = [k for sid, _, items in NAV_SECTIONS if sid == "data" for _, k in items]
    assert keys[keys.index("hypeddit") + 1] == "saisie_tresorerie", keys
    assert ROUTES["saisie_tresorerie"] == "views.saisie_tresorerie"


def test_the_entry_page_holds_the_revenue_the_deletion_and_the_costs() -> None:
    calls = _calls(_VIEWS / "saisie_tresorerie.py", "show")
    assert {"_render_entry_form", "_render_delete", "_render_cost_entry"} <= calls, calls


def test_the_treasury_page_writes_nothing_and_opens_both_doors() -> None:
    reached = (_calls(_VIEWS / "imusician.py", "show")
               | _calls(_VIEWS / "imusician.py", "_render_treasury")
               | _calls(_VIEWS / "revenue_forecast.py", "render_artist_money"))
    assert not reached & {"_render_entry_form", "_render_delete", "_render_cost_entry"}, reached
    doors = _calls(_VIEWS / "imusician.py", "_render_entry_buttons")
    assert {"goto", "goto_tab"} <= doors, doors
