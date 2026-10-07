"""R454 — a navigation button reaches the page it names.

Type: Test
Uses: src/dashboard (AST), src/dashboard/utils/nav_sections.NAV_SECTIONS,
      src/dashboard/routes.resolve_alias, src/dashboard/utils/navigation.url_key

Owner, 2026-10-07: « Le bouton Ouvrir Road to Algo ne fonctionne pas. » Two causes:
- `algo_preview.py` called `bouton_vers(...)` as a bare statement: its contract is « True
  if clicked AND open, the caller navigates », so the click was thrown away;
- `goto("upgrade")` (plan_gate, absence_cta), `?page=upgrade` (auth.require_plan) and the
  URL mirror named `upgrade`, a key of ROUTES that is neither in the menu nor an alias:
  `resolve_nav_page` sends it home.

Sweep (sibling-sweeper, 2026-10-07): A — 58 raw button calls → 57 excluded (on_click,
disabled, value read) → 1 live; B — ~60 navigation emissions → ~56 visible or public →
2 live + 2 to settle (require_plan, URL mirror), all four fixed here.

The trap the sweep named: « the key is routed » passes on `upgrade`; the property is « the
key, once resolved, is a MENU key ».

Mutation record (2026-10-07): `if bouton_vers` → bare call → red; `goto(page_key)` →
`goto("upgrade")` in plan_gate → red; `url_key` returning `page` → red.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.routes import resolve_alias
from src.dashboard.utils.navigation import url_key
from src.dashboard.utils.nav_sections import NAV_SECTIONS

SRC = Path(__file__).resolve().parents[1] / "src" / "dashboard"
MENU = {key for _, _, items in NAV_SECTIONS for _, key in items}
NAVIGATORS = {"goto", "bouton_vers"}
# Pre-authentication routes answered by app.main() before any menu exists.
PUBLIC = {"register", "privacy", "verify", "unsubscribe", "onboarding", "login"}


def _trees():
    for path in sorted(SRC.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def _name(func: ast.expr) -> str:
    return getattr(func, "id", None) or getattr(func, "attr", "")


def literal_targets(tree: ast.AST) -> list[tuple[int, str]]:
    """(line, key) for every literal page a navigation call or `query_params["page"]=` names."""
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and _name(node.func) in NAVIGATORS and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            out.append((node.lineno, node.args[0].value))
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Subscript) and _name(tgt.value) == "query_params"
                        and getattr(tgt.slice, "value", None) == "page"
                        and node.value.value not in PUBLIC):
                    out.append((node.lineno, node.value.value))
    return out


def discarded_clicks(tree: ast.AST) -> list[int]:
    """Lines where `bouton_vers(...)` is a bare statement — its True is thrown away."""
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
            and _name(n.value.func) == "bouton_vers"]


def test_every_literal_navigation_target_is_a_menu_page():
    bad = [f"{p.relative_to(SRC)}:{line} → {key!r}"
           for p, tree in _trees() for line, key in literal_targets(tree)
           if resolve_alias(key)[0] not in MENU]
    assert not bad, "these buttons land on home, not on their page:\n" + "\n".join(bad)


def test_no_click_of_bouton_vers_is_thrown_away():
    bad = [f"{p.relative_to(SRC)}:{line}" for p, tree in _trees() for line in discarded_clicks(tree)]
    assert not bad, "bouton_vers returns the click; the caller must navigate:\n" + "\n".join(bad)


def test_the_url_mirrors_the_page_asked_for_not_the_wall():
    assert url_key("upgrade", "trigger_algo") == "trigger_algo"
    assert url_key("home", "home") == "home"
    assert url_key("upgrade", None) == "upgrade"


def test_the_detectors_see_the_defects_they_are_written_for():
    """Non-vacuity: on the exact defect code each detector bites, and not on the fix."""
    assert literal_targets(ast.parse('goto("upgrade")')) == [(1, "upgrade")]
    assert resolve_alias("upgrade")[0] not in MENU
    assert literal_targets(ast.parse('st.query_params["page"] = "upgrade"')) == [(1, "upgrade")]
    assert discarded_clicks(ast.parse('bouton_vers("trigger_algo", ouvert="o", ferme="f")')) == [1]
    assert not discarded_clicks(ast.parse('if bouton_vers("x", ouvert="o", ferme="f"):\n    goto("x")'))
