"""Les couleurs SÉMANTIQUES sont attribuables, y compris par un daltonien.

Type: Test
Uses: src/dashboard/utils/colorimetry (CIEDE2000 + Viénot/Brettel, stdlib)
Depends on: src/dashboard/utils/semantic_colors
Persists in: nothing

⚠️ Sans ce garde, `semantic_colors.py` serait une liste de littéraux avec un docstring
qui AFFIRME qu'ils sont mesurés — et ce dépôt a déjà payé cette forme : la palette de
plateformes portait sa mesure dans un commentaire, le validateur vivait dans un autre
dépôt, et elle a changé deux fois sans que rien ne puisse la vérifier.
"""
from __future__ import annotations

import itertools

import pytest

from src.dashboard.utils.colorimetry import de2000, lightness, simulate
from src.dashboard.utils.semantic_colors import (
    BANDE_CLARTE, PLANCHER, SEMANTIQUES,
)

_VISIONS = ("normal", "deutan", "protan")


def _ecart(a: str, b: str, vision: str) -> float:
    if vision != "normal":
        a, b = simulate(a, vision), simulate(b, vision)
    return de2000(a, b)


@pytest.mark.parametrize("paire", list(itertools.combinations(sorted(SEMANTIQUES), 2)),
                         ids=lambda p: f"{p[0]}-{p[1]}")
@pytest.mark.parametrize("vision", _VISIONS)
def test_every_semantic_pair_clears_the_floor(paire, vision: str) -> None:
    """Six paires × trois visions. Une seule sous le plancher rend le module faux."""
    a, b = paire
    d = _ecart(SEMANTIQUES[a], SEMANTIQUES[b], vision)
    assert d >= PLANCHER, (
        f"{a} ({SEMANTIQUES[a]}) ↔ {b} ({SEMANTIQUES[b]}) : ΔE {d:.1f} en {vision}, "
        f"sous le plancher de {PLANCHER}.\n"
        "Ces couleurs existent POUR être attribuables — une paire sous le plancher les "
        "rend équivalentes à ce qu'elles remplacent. Rechercher la position dans la "
        "famille de teinte, ne pas déplacer le plancher.")


@pytest.mark.parametrize("nom", sorted(SEMANTIQUES))
def test_every_semantic_colour_sits_in_the_declared_band(nom: str) -> None:
    """La bande de clarté que le module DÉCLARE appliquer.

    ⚠️ Ce test existe parce que le premier jet ne la respectait pas : `ATTENTION` était à
    L* 78,1 pour une bande qui s'arrête à 77, et c'est une RELECTURE qui l'a vu, pas un
    garde. Une contrainte écrite dans un docstring et nulle part ailleurs n'est pas une
    contrainte.
    """
    L = lightness(SEMANTIQUES[nom])
    lo, hi = BANDE_CLARTE
    assert lo <= L <= hi, (
        f"{nom} ({SEMANTIQUES[nom]}) a L* {L*100:.1f}, hors de la bande déclarée "
        f"{lo*100:.0f}–{hi*100:.0f}. Le module affirme s'y tenir : soit la couleur "
        "rentre, soit la bande change AVEC sa justification.")


def test_the_measurement_would_refuse_the_pair_this_module_exists_to_replace() -> None:
    """ANTI-VACUITÉ, et le chiffre qui résume R133.

    Un garde qui n'a jamais refusé quoi que ce soit ne prouve pas qu'il sait refuser. On
    lui donne donc la paire RÉELLE du parc — un vert et un rouge ordinaires, à la même
    clarté — et il doit la déclarer illisible. Si ce test devenait vert, la mesure aurait
    cessé de mesurer et les six assertions ci-dessus ne diraient plus rien.
    """
    d = _ecart("#27751a", "#a32929", "deutan")
    assert d < 5.0, (
        f"ΔE {d:.1f} : la mesure juge distinguables un vert et un rouge ordinaires à la "
        "même clarté. C'est la paire qui a mis 19 figures sous le plancher ; si elle "
        "passe, c'est la colorimétrie qui est cassée, pas la palette qui s'est améliorée.")


def test_lightness_is_what_separates_them_not_hue() -> None:
    """L'affirmation centrale du module, vérifiée plutôt qu'écrite.

    `BON` et `MAUVAIS` doivent être séparés d'au moins 15 points de L*. Un correctif
    futur qui « rapprocherait les teintes pour faire plus joli » en les ramenant à la
    même clarté rendrait la paire illisible — et le test de plancher le dirait, mais sans
    dire POURQUOI. Celui-ci nomme la cause.
    """
    ecart = abs(lightness(SEMANTIQUES["bon"]) - lightness(SEMANTIQUES["mauvais"])) * 100
    assert ecart >= 15.0, (
        f"BON et MAUVAIS ne sont séparés que de {ecart:.1f} points de clarté. La teinte "
        "seule ne les distingue pas en deuteranopie — mesuré : un rouge à la clarté du "
        "vert est à ΔE 1,6 à TOUTES les saturations.")
