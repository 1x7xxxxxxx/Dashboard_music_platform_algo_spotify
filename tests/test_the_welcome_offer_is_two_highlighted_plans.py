"""R457 — the welcome offer shows two plans, each highlighted in its own colour, no blabla.

Type: Test
Uses: src/dashboard/views/onboarding.py (AST + PLAN_HIGHLIGHT)

Owner, 2026-10-07: « supprimer la partie Votre compte a été créé avec le plan Premium…
jusqu'à … l'export CSV reste gratuit » ; « une petite ligne » between Free and Premium ;
each « en surlignement d'une couleur différente ».

Mutation record (2026-10-07): `welcome_body` call restored → red; both colours set to
`blue` → red; `_PLAN_RULE` column removed (`st.columns(2)`) → red.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.views import onboarding

VIEW = Path(onboarding.__file__)
TREE = ast.parse(VIEW.read_text(encoding="utf-8"))


def _t_keys(tree: ast.AST) -> set[str]:
    return {n.args[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "t" and n.args
            and isinstance(n.args[0], ast.Constant)}


def _rule_is_rendered(tree: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "markdown"
               and n.args and getattr(n.args[0], "id", "") == "_PLAN_RULE"
               for n in ast.walk(tree))


def test_the_two_redundant_lines_are_gone():
    assert not {"onboarding.welcome_body", "onboarding.b2_after"} & _t_keys(TREE)


def test_each_plan_has_its_own_colour():
    assert set(onboarding.PLAN_HIGHLIGHT) == {"free", "premium"}
    assert len(set(onboarding.PLAN_HIGHLIGHT.values())) == 2


def test_a_rule_separates_the_plans():
    assert _rule_is_rendered(TREE)
    assert "border-left" in onboarding._PLAN_RULE


def test_the_detectors_see_the_defect():
    defect = ast.parse('t("onboarding.welcome_body", "x")\nst.markdown("---")')
    assert "onboarding.welcome_body" in _t_keys(defect) and not _rule_is_rendered(defect)
    assert _rule_is_rendered(ast.parse("st.markdown(_PLAN_RULE, unsafe_allow_html=True)"))
