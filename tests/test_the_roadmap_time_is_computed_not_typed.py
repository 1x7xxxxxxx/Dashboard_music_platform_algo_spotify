"""La durée annoncée à l'artiste doit être SOMMÉE, jamais tapée — dans les deux langues.

Type: Test
Uses: ast, i18n catalogs, content.platform_value
Depends on: src/dashboard/views/onboarding.py, i18n_catalog/onboarding.py
Persists in: nothing

The defect this guards
---------------------
The welcome step announces how long the setup costs ("≈7 min for the two recommended
ones"). That number is only true because it is SUMMED from `effort_min`, the same field
each checkbox reads a few lines below. Typed as a literal — in either language — it
becomes a claim nothing recomputes: raise Instagram from 5 to 8 minutes and the artist
is told 7 forever, while the checkbox right below says 8.

Le garde a DÉMÉNAGÉ DEUX FOIS le 2026-09-04, comme son propre message le demandait
(« if the roadmap moved, move this guard with it »). D'abord de « 🗺️ Ta mise en route »
— supprimée, elle décrivait un parcours qu'on est en train de faire — vers la ligne de
recommandation. Puis de cette ligne, supprimée à son tour quand la première colonne du
sélecteur s'est mise à dire la même chose en la montrant, vers `_step_welcome`, où la
durée sommée subsiste sur le BOUTON : « Configurer ma sélection (3) → ≈9 min ».

La CLAIM protégée n'a pas changé d'un mot en trois déménagements — une durée annoncée à
un artiste doit être sommée. C'est la surface qui la porte qui bouge, et c'est
exactement pourquoi le garde vise une fonction nommée plutôt qu'un libellé : un test
ancré sur « ⭐ Recommandé pour démarrer » serait mort trois fois.

The translation is the likelier place for it to happen: a translator who receives
"≈7 min" as source text has no reason to keep a `{mins}` placeholder.

What this asserts
-----------------
1. `_step_welcome` actually calls `total_effort` — it does not carry its own sum.
2. Every language's recommendation string keeps the `{mins}` and `{names}` placeholders.
3. No string in that function hard-codes a minute count that could contradict them.

Point 3 deliberately allows "1 min" and "0 min": those are fixed costs, not sums over
platforms.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from src.dashboard.content.platform_value import RECOMMENDED, total_effort
from src.dashboard.utils.i18n_catalog.onboarding import EN

_VIEW = Path(__file__).resolve().parents[1] / "src/dashboard/views/onboarding.py"
_FN = "_step_welcome"


def _function_node() -> ast.FunctionDef:
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == _FN:
            return node
    raise AssertionError(
        f"{_VIEW.name} no longer defines {_FN}(). If the roadmap moved, move this "
        "guard with it — the claim it protects is a duration shown to artists."
    )


def _string_literals(node: ast.FunctionDef) -> list[str]:
    """Every string the function can SHOW — its docstring excluded.

    The docstring explains the guard to the next reader; it never reaches an artist.
    Scanning it made this test fail on its own prose, which is the recurring shape of
    a guard whose predicate matches the symptom instead of the question.
    """
    body = node.body[1:] if ast.get_docstring(node) is not None else node.body
    out: list[str] = []
    for stmt in body:
        out += [n.value for n in ast.walk(stmt)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return out


def test_the_roadmap_sums_the_platform_efforts_instead_of_carrying_a_number():
    calls = {
        n.func.id for n in ast.walk(_function_node())
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "total_effort" in calls, (
        f"{_FN}() no longer calls total_effort(). The minutes it shows would then be "
        "independent of effort_min, which the platform matrix on the next step reads — "
        "the two surfaces can now state different durations for the same work."
    )


def test_the_recommended_setup_has_a_duration_worth_stating():
    mins = total_effort(RECOMMENDED)
    assert RECOMMENDED, "no platform is flagged recommended — the roadmap has nothing to size"
    assert mins > 0, (
        "total_effort(RECOMMENDED) is 0; the roadmap would promise a setup that costs "
        "nothing, which no artist will believe."
    )


def test_no_language_drops_the_placeholders():
    fr = [s for s in _string_literals(_function_node()) if "{mins}" in s]
    assert fr, (
        "no string in the welcome step substitutes {mins} any more: the duration is "
        "either gone or typed as a literal."
    )
    assert any("{mins}" in s and "{n}" in s for s in fr), (
        "the button lost {mins} or {n}: the artist reads a placeholder, or a count "
        "and a duration that nothing recomputes."
    )
    en = EN.get("onboarding.configure_selection")
    assert en, ("the English catalog has no onboarding.configure_selection — English "
                "artists read the French button")
    assert "{mins}" in en and "{n}" in en, (
        f"the English button lost a placeholder: {en!r}. .format() would raise or, "
        "worse, silently present a duration nothing recomputes."
    )


def test_no_translation_hard_codes_a_platform_sum():
    """A digit before 'min' is allowed only for the two fixed costs, 1 and 0."""
    suspects: list[tuple[str, str]] = []
    for label, text in (("fr", "\n".join(_string_literals(_function_node()))),
                        ("en", EN.get("onboarding.configure_selection", ""))):
        for found in re.findall(r"(\d+)\s*min", text):
            if found not in {"0", "1"}:
                suspects.append((label, found))
    assert not suspects, (
        f"a minute count is typed into the roadmap text: {suspects}. Only the fixed "
        "costs (1 min to tick boxes, 0 min to wait for the nightly run) may be literals; "
        "anything summed over platforms must come through {mins}."
    )
