"""R457 — the welcome offer shows two plans, each highlighted in its own colour, no blabla.

Type: Test
Uses: src/dashboard/views/onboarding.py (AST + PLAN_HIGHLIGHT)

Owner, 2026-10-07: « supprimer la partie Votre compte a été créé avec le plan Premium…
jusqu'à … l'export CSV reste gratuit » ; « une petite ligne » between Free and Premium ;
each « en surlignement d'une couleur différente ».

Mutation record (2026-10-07): `welcome_body` call restored → red; both colours set to
`blue` → red; `border=True` removed from the plan columns → red. The first form of
the line was a raw `<div>`: refused by the setup page's no-raw-HTML guard, so the line
is the columns' native border.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.views import onboarding

VIEW = Path(onboarding.__file__)


def _tree() -> ast.AST:
    return ast.parse(VIEW.read_text(encoding="utf-8"))


def _t_keys(tree: ast.AST) -> set[str]:
    return {n.args[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "t" and n.args
            and isinstance(n.args[0], ast.Constant)}


def _rule_is_rendered(tree: ast.AST) -> bool:
    """A `st.columns(..., border=True)` call — the native line between the plans."""
    return any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "columns"
               and any(k.arg == "border" and getattr(k.value, "value", None) is True
                       for k in n.keywords)
               for n in ast.walk(tree))


def test_the_two_redundant_lines_are_gone():
    assert not {"onboarding.welcome_body", "onboarding.b2_after"} & _t_keys(_tree())


def test_each_plan_has_its_own_colour():
    assert set(onboarding.PLAN_HIGHLIGHT) == {"free", "premium"}
    assert len(set(onboarding.PLAN_HIGHLIGHT.values())) == 2


def test_a_rule_separates_the_plans():
    assert _rule_is_rendered(_tree())


def test_the_detectors_see_the_defect():
    defect = ast.parse('t("onboarding.welcome_body", "x")\nst.columns(2)')
    assert "onboarding.welcome_body" in _t_keys(defect) and not _rule_is_rendered(defect)
    assert _rule_is_rendered(ast.parse("st.columns(2, border=True)"))
