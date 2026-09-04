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

from src.dashboard.content.platform_value import BY_KEY, RECOMMENDED, total_effort
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


def test_no_surface_types_a_platform_duration_by_hand():
    """La question, sans sa surface — et c'est le troisième déménagement.

    Elle a vécu dans « 🗺️ Ta mise en route », puis dans la ligne de recommandation,
    puis sur le bouton « Configurer ma sélection ({n}) → ≈{mins} min ». Le 2026-09-05
    le sélecteur entier a disparu — « on ne va pas demander les cases à cocher » — et
    avec lui la dernière surface qui annonçait une durée.

    Ancré sur une fonction nommée, ce garde serait mort trois fois et vacuous la
    quatrième. La revendication, elle, n'a pas bougé : **une durée de plateforme
    montrée à un artiste est SOMMÉE, jamais tapée.** Il n'y en a plus une seule
    aujourd'hui ; le jour où l'on en remet une, elle passera par `total_effort` ou ce
    test rougira.

    C'est la différence entre retirer un garde parce que sa surface est partie — ce
    qui arrête de surveiller la propriété — et le suivre là où la propriété vit.
    """
    import re as _re
    from pathlib import Path as _Path

    # Les DEUX fichiers qui portent le vocabulaire du coût de mise en route. Balayer
    # tout `src/dashboard` attrapait « session expirée après 15 min » et « les données
    # arrivent sous ~2 min » — des délais réels, sans rapport avec l'effort d'une
    # plateforme. Un prédicat qui hurle sur ce qu'il ne vise pas se fait désarmer.
    root = _Path(__file__).resolve().parents[1] / "src" / "dashboard"
    scope = [root / "views" / "onboarding.py",
             root.parent / "dashboard" / "content" / "platform_value.py"]
    typed = []
    for path in scope:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            for found in _re.findall(r"(\d+)\s*min\b", node.value):
                # « 1 min » et « 0 min » sont des coûts FIXES, pas des sommes.
                if found not in {"0", "1"}:
                    typed.append(f"{path.name}:{node.lineno} → « {found} min »")
    assert not typed, (
        "Ces chaînes annoncent une durée de plateforme écrite à la main :\n  "
        + "\n  ".join(typed)
        + "\n\nElle doit venir de `total_effort()`, qui somme les `effort_min` que "
          "les cases et la matrice lisent — sinon deux surfaces annoncent des durées "
          "différentes pour le même travail."
    )


def test_the_recommended_setup_has_a_duration_worth_stating():
    mins = total_effort(RECOMMENDED)
    assert RECOMMENDED, "no platform is flagged recommended — the roadmap has nothing to size"
    assert mins > 0, (
        "total_effort(RECOMMENDED) is 0; the roadmap would promise a setup that costs "
        "nothing, which no artist will believe."
    )


def test_the_summing_helper_still_exists_and_sums():
    """Non-vacuité : sans `total_effort`, le test au-dessus n'interdirait rien.

    Un garde qui interdit d'écrire une durée à la main ne vaut que s'il existe une
    façon de la calculer. Les deux assertions précédentes remplaçaient la
    vérification des `{mins}` / `{names}` d'un libellé qui n'existe plus.
    """
    from src.dashboard.content.platform_value import PLATFORM_VALUES

    keys = [p.key for p in PLATFORM_VALUES][:3]
    assert total_effort(keys) == sum(BY_KEY[k].effort_min for k in keys)
    assert total_effort([]) == 0
    assert total_effort(["inconnue"]) == 0, (
        "une clé inconnue doit valoir 0, pas lever : ce total s'affiche")


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
