"""Deux aires de la figure peuvent être ATTRIBUÉES, y compris par un daltonien.

Type: Test
Uses: pytest (colorimétrie en stdlib)
Depends on: src/dashboard/utils/platform_chart.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
La palette a été refusée une fois, et la mesure vivait dans un commentaire. Le
2026-09-08, le premier jet prenait les couleurs de MARQUE exactes :

    #1DB954 · #FF0000 · #FF5500
    youtube ↔ soundcloud   ΔE 9.6 (vision normale) · 4.6 (deutan)

Deux aires qu'on ne peut pas attribuer — la définition d'une figure illisible. Le
verdict venait d'un validateur EXTERNE (`node scripts/validate_palette.js`, skill
`dataviz`), absent de ce dépôt : la mesure n'était donc rejouable nulle part, et le
2026-09-12 la palette a changé de nouveau sans que rien ne puisse la vérifier.

Ce fichier porte la mesure elle-même — CIEDE2000 et la simulation dichromate de
Viénot/Brettel, en stdlib. Il ne remplace pas la skill ; il rend son verdict
reproductible ici, ce qui est la différence entre une règle et un souvenir.

⚠️ LES DEUX PLANCHERS NE SONT PAS LES MÊMES, et c'est une borne mesurée, pas un
confort. La bande de clarté du mode sombre (0,48–0,67) laisse 0,19 de latitude pour
séparer trois teintes chaudes — Spotify vert, YouTube rouge, SoundCloud orange,
Apple magenta. Balayage exhaustif le 2026-09-12 : le MAXIMUM atteignable y est
**13,9** (14,6 sans Apple), contre 16,9 en clair. Un plancher de 15 en sombre est
donc un plancher que rien ne peut franchir ; le fixer là rendrait le garde rouge à
vie, donc ignoré. Il est à 13,5, et la marge au-dessus du maximum est de 0,4 : la
palette sombre ne peut pas se dégrader sans que ce fichier le dise.

Mutation — 2026-09-12 : Apple remise à son rouge de marque `#fa243c`, ce garde la
nomme (ΔE 3,0 contre YouTube en deutan) ; remise en magenta, il passe.
"""
from __future__ import annotations

import itertools

import pytest

from src.dashboard.utils.colorimetry import de2000, lightness, report, simulate
from src.dashboard.utils.platform_chart import _PALETTE_DARK, _PALETTE_LIGHT

# Planchers, et le pourquoi de leur écart est dans le docstring.
_FLOOR_LIGHT = 15.0
_FLOOR_DARK = 13.5
_BAND_LIGHT = (0.43, 0.77)
_BAND_DARK = (0.48, 0.67)


def unattributable_pairs(pal: dict, floor: float) -> list[tuple[str, str, str, float]]:
    """(vision, a, b, ΔE) for every pair below `floor`, in normal AND dichromat vision."""
    out = []
    for a, b in itertools.combinations(sorted(pal), 2):
        for vision, ca, cb in (("normale", pal[a], pal[b]),
                               ("deutan", simulate(pal[a], "deutan"), simulate(pal[b], "deutan")),
                               ("protan", simulate(pal[a], "protan"), simulate(pal[b], "protan"))):
            d = de2000(ca, cb)
            if d < floor:
                out.append((vision, a, b, d))
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity through the guard's own loop: the exact brand colours refused on
    2026-09-08 (YouTube red, SoundCloud orange) are named as a deutan pair; the shipped
    light palette is not."""
    brand = {"youtube": "#FF0000", "soundcloud": "#FF5500"}
    pairs = unattributable_pairs(brand, _FLOOR_LIGHT)
    assert ("deutan", "soundcloud", "youtube") in [(v, a, b) for v, a, b, _ in pairs]
    # A pair only a DICHROMAT confuses — ΔE 67 in normal vision, 9 in deutan. Without
    # it, a loop that forgot to simulate would still pass on red vs orange above.
    only_deutan = {"soundcloud": "#FF5500", "spotify": "#1DB954"}
    assert [v for v, *_ in unattributable_pairs(only_deutan, _FLOOR_LIGHT)] == ["deutan"]
    assert unattributable_pairs(_PALETTE_LIGHT, _FLOOR_LIGHT) == []


@pytest.mark.parametrize("theme,pal,floor,band", [
    ("clair", _PALETTE_LIGHT, _FLOOR_LIGHT, _BAND_LIGHT),
    ("sombre", _PALETTE_DARK, _FLOOR_DARK, _BAND_DARK),
])
def test_every_pair_of_areas_can_be_told_apart(theme, pal, floor, band) -> None:
    """Chaque paire, en vision normale ET dichromate. Une seule suffit à casser."""
    bad = [f"  {theme}/{vision:<8} {a} ↔ {b}  ΔE {d:4.1f}  < {floor}"
           for vision, a, b, d in unattributable_pairs(pal, floor)]
    assert not bad, (
        f"deux aires de la figure ne peuvent pas être attribuées en thème {theme} :\n"
        + "\n".join(bad)
        + "\n\nC'est le défaut du 2026-09-08 — les couleurs de marque exactes, "
          "refusées à ΔE 4,6. Chercher la meilleure position DANS la famille de "
          "marque, jamais la teinte exacte.")


@pytest.mark.parametrize("theme,pal,band", [
    ("clair", _PALETTE_LIGHT, _BAND_LIGHT), ("sombre", _PALETTE_DARK, _BAND_DARK),
])
def test_every_colour_sits_in_its_theme_lightness_band(theme, pal, band) -> None:
    """Hors bande, l'aire disparaît dans le fond ou brûle l'écran."""
    out = [f"  {k} {v} L={lightness(v):.2f} hors {band}"
           for k, v in sorted(pal.items()) if not band[0] <= lightness(v) <= band[1]]
    assert not out, f"thème {theme} :\n" + "\n".join(out)


def test_the_measurement_reproduces_the_refusal_that_created_this_rule() -> None:
    """NON-VACUITÉ : le validateur doit REFUSER ce qui a été refusé le 2026-09-08.

    Sans ce test, une erreur de formule rendrait tout vert et le fichier entier
    serait un garde qui ne garde rien — la forme que ce dépôt a payée le plus
    souvent. Les couleurs de marque exactes sont donc rejouées ici : leur ΔE deutan
    mesuré à l'époque était 4,5 ; on exige seulement qu'il reste très en dessous du
    plancher, pas un chiffre au dixième près.
    """
    d = de2000(simulate("#FF0000", "deutan"), simulate("#FF5500", "deutan"))
    assert d < 8.0, (
        f"le rouge YouTube et l'orange SoundCloud mesurent ΔE {d:.1f} en deutan — "
        "le validateur ne reproduit plus le refus du 2026-09-08, donc il ne mesure "
        "plus ce qu'il prétend mesurer")
