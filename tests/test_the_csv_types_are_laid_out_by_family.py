"""Guard: the drop tab shows its accepted types in columns, distributors last.

Type: Utility
Uses: ast, src.dashboard.content.csv_guides
Triggers: pytest
Persists in: nothing

Error class `layout-keyed-by-a-hand-written-list`.

Asked 2026-09-06: one drop zone, the types laid out in columns, and the distributor
block at the very bottom, under Spotify for Artists and Apple Music.

The layout used to be keyed by `_SIDE_BY_SIDE = ("s4a", "apple")` in the renderer,
with `rest = [everything else]` rendered underneath. Two facts made that a defect
rather than a shortcut: the leftover group was LABELLED nothing, so a guide added
tomorrow silently inherited the bottom row; and once that row is titled
"distributors" — which is what was asked for — a new listening platform would be
filed under a heading that is simply false, with nothing to report it.

`PlatformGuide.family` moves the question into the data, where adding a guide forces
an answer. These assertions check the two things a reader of the page can see: that
every guide declares a family, and that the renderer derives from it.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from src.dashboard.content import csv_guides_st
from src.dashboard.content.csv_guides import (
    CSV_GUIDES,
    FAMILY_DISTRIBUTOR,
    FAMILY_PLATFORM,
)

_FAMILIES = {FAMILY_PLATFORM, FAMILY_DISTRIBUTOR}


def test_every_guide_declares_a_family():
    """A guide with no family would be laid out by accident."""
    unknown = [(g.key, g.family) for g in CSV_GUIDES if g.family not in _FAMILIES]
    assert not unknown, (
        f"{unknown} : famille inconnue. Ajoute-la à `csv_guides` — la mise en page "
        f"la lit, et une valeur hors de {sorted(_FAMILIES)} tombe dans aucune colonne."
    )


def test_both_families_are_populated():
    """Otherwise every assertion below is vacuously true."""
    for family in _FAMILIES:
        assert [g for g in CSV_GUIDES if g.family == family], (
            f"aucun guide de famille {family!r} — ce fichier ne prouverait rien")


def test_the_two_listening_platforms_come_first():
    """S4A and Apple are what an artist comes for; the order is the page order."""
    families = [g.family for g in CSV_GUIDES]
    first_distributor = families.index(FAMILY_DISTRIBUTOR)
    assert FAMILY_PLATFORM not in families[first_distributor:], (
        "une plateforme d'écoute est déclarée APRÈS un distributeur : la page rend "
        f"CSV_GUIDES dans l'ordre, donc elle apparaîtrait sous le bloc revenus. "
        f"Ordre lu : {families}")


def test_the_renderer_reads_the_family_and_not_a_list_of_keys():
    """The regression that matters: a hard-coded tuple coming back."""
    src = inspect.getsource(csv_guides_st)
    tree = ast.parse(src)

    # Aucune constante du module ne doit énumérer des clés de guides. C'est la forme
    # exacte de `_SIDE_BY_SIDE = ("s4a", "apple")`.
    keys = {g.key for g in CSV_GUIDES}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        literals = {n.value for n in ast.walk(node.value)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        offending = literals & keys
        assert not offending, (
            f"{ast.unparse(node.targets[0])} énumère des clés de guides "
            f"({sorted(offending)}) : la mise en page redevient une liste tenue à la "
            "main, et un guide ajouté demain tombera dans le mauvais groupe sans que "
            "rien ne le dise. Lis `PlatformGuide.family`.")

    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert {"FAMILY_PLATFORM", "FAMILY_DISTRIBUTOR"} <= names, (
        "le rendu ne lit plus les familles — il range donc par autre chose")


def test_the_distributor_block_is_rendered_after_the_platforms():
    """Bottom of the page, one block, as asked."""
    # Par AST : l'ORDRE des `ast.Name` dans la fonction, pas l'ordre des caractères
    # dans son texte. Une docstring qui nomme les deux familles suffirait à satisfaire
    # `src.index(...)` — et ce fichier en a une.
    tree = ast.parse(inspect.getsource(csv_guides_st))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "render_csv_guides")
    order = [n.id for n in ast.walk(fn)
             if isinstance(n, ast.Name) and n.id in
             ("FAMILY_PLATFORM", "FAMILY_DISTRIBUTOR")]
    assert order and order[0] == "FAMILY_PLATFORM", (
        f"les distributeurs sont traités avant les plateformes d'écoute : {order}")
    # Le bloc distributeurs est UN expander, pas deux volets de même rang.
    expanders = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "expander"]
    assert len(expanders) == 1, (
        f"{len(expanders)} expanders ouverts directement par `render_csv_guides` — "
        "les distributeurs doivent tenir dans UN seul bloc en bas de page.")
