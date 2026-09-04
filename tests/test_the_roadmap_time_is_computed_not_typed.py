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

Le garde a DÉMÉNAGÉ le 2026-09-04, comme son propre message le demandait
(« if the roadmap moved, move this guard with it »). La section « 🗺️ Ta mise en route »
a été supprimée — elle décrivait un parcours qu'on est en train de faire — et la seule
durée sommée qu'elle portait vit maintenant dans la ligne de recommandation, juste sous
« Coche ce que tu veux configurer ». La CLAIM protégée n'a pas changé d'un mot ; c'est
la fonction qui la porte qui a changé de nom.

The translation is the likelier place for it to happen: a translator who receives
"≈7 min" as source text has no reason to keep a `{mins}` placeholder.

What this asserts
-----------------
1. `_platform_picker` actually calls `total_effort` — it does not carry its own sum.
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
_FN = "_platform_picker"


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
    fr = [s for s in _string_literals(_function_node()) if "{mins}" in s or "min" in s]
    assert any("{mins}" in s and "{names}" in s for s in fr), (
        "the French recommendation string lost {mins} or {names}: the duration is no "
        "longer substituted and the artist reads the placeholder or a stale literal."
    )
    en = EN.get("onboarding.reco_line")
    assert en, "the English catalog has no onboarding.reco_line — English artists see French"
    assert "{mins}" in en and "{names}" in en, (
        f"the English roadmap lost a placeholder: {en!r}. .format() would raise or, worse, "
        "silently present a duration nothing recomputes."
    )


def test_no_translation_hard_codes_a_platform_sum():
    """A digit before 'min' is allowed only for the two fixed costs, 1 and 0."""
    suspects: list[tuple[str, str]] = []
    for label, text in (("fr", "\n".join(_string_literals(_function_node()))),
                        ("en", EN.get("onboarding.reco_line", ""))):
        for found in re.findall(r"(\d+)\s*min", text):
            if found not in {"0", "1"}:
                suspects.append((label, found))
    assert not suspects, (
        f"a minute count is typed into the roadmap text: {suspects}. Only the fixed "
        "costs (1 min to tick boxes, 0 min to wait for the nightly run) may be literals; "
        "anything summed over platforms must come through {mins}."
    )
