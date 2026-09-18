"""Une figure NEUVE doit pouvoir être attribuée, y compris par un daltonien.

Type: Test
Uses: tools/dev/figure_contrast_report (colorimétrie de src/dashboard/utils/colorimetry)
Depends on: .claude/dev-docs/figure-contrast-baseline.json
Persists in: nothing

Pourquoi cette porte ne couvre QUE le diff
------------------------------------------
Mesuré le 2026-09-17 puis resserré trois fois : **19 figures** du parc sont sous le
plancher d'attribution de 15. `code-critic` a rendu **BUILD-MODIFIED** sur R133, et le
refus porte précisément sur l'idée de les migrer d'un coup — un garde bloquant posé sur
19 sites déjà rouges n'a que deux issues : on le désactive, ou on bâcle 19 migrations
visuelles sans les regarder. Les deux détruisent le garde.

La porte est donc un CLIQUET : les 19 sont enregistrées, elles ne bloquent rien, et le
fichier de référence ne peut que rétrécir. Ce qui bloque, c'est une figure **neuve** ou
une paire de couleurs **changée** — là où la correction coûte une ligne au lieu d'une
séance de relecture visuelle.

⚠️ Le plancher de 15 a été calibré sur des AIRES EMPILÉES, où la teinte est le seul
canal d'attribution. Une figure qui écrit sa valeur au bout de chaque barre ou dont les
séries occupent des positions distinctes reste lisible en dessous. Le rapport signale ce
cas (`attenue`) sans l'exempter : décider qu'un canal de secours suffit demande un œil,
pas un prédicat — et le mettre dans le prédicat rendrait le chiffre incontestable au
mauvais sens du terme.

⚠️ **Trois chiffres successifs pour la même grandeur, et les trois écarts sont le même
défaut** : 26 (par FONCTION — mélangeait les figures d'un même `show()`), 28 (par FIGURE
— mélangeait les PANNEAUX d'un `make_subplots`), 19 (par PANNEAU, fragment borné à son
rendu). `_tab_algos.py:90` est le cas d'école : `#1DB954` vit en `row=1`, `#FF6B6B` en
`row=2`, et la mesure par figure les opposait à ΔE 3,1 alors qu'aucun œil n'a jamais à
les attribuer l'un contre l'autre.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dev.figure_contrast_report import (  # noqa: E402
    PLANCHER, _panneaux, _pire_paire, cle, figures,
)

_BASELINE = ROOT / ".claude" / "dev-docs" / "figure-contrast-baseline.json"


def _reference() -> dict:
    return json.loads(_BASELINE.read_text(encoding="utf-8"))


def test_the_baseline_names_something_real() -> None:
    """Anti-vacuité : une référence vide rendrait la porte ci-dessous toujours verte."""
    ref = _reference()
    assert ref["total"] >= 1, "la référence est vide — la porte n'affirmerait plus rien"
    assert sum(ref["cles"].values()) == ref["total"], (
        "le compte par clé et le total ne disent pas la même chose : la référence a été "
        "éditée à la main d'un côté seulement")


def test_the_measurement_still_finds_figures_at_all() -> None:
    """Si le détecteur cesse de voir des figures, tout le reste devient vert pour rien."""
    toutes = figures()
    assert len(toutes) >= 20, (
        f"seulement {len(toutes)} figure(s) à ≥2 couleurs de série trouvées. Le détecteur "
        "a cessé de voir le parc — un renommage de `go.Figure`, un déplacement des vues, "
        "ou un motif d'ouverture devenu faux. Toutes les assertions ci-dessous seraient "
        "alors vertes sans rien garder.")


def test_a_figure_that_is_not_in_the_baseline_must_pass_the_floor() -> None:
    """LA PORTE. Neuve ou modifiée ⇒ elle doit être attribuable.

    Une figure déjà connue est un plafond qui descendra ; une figure neuve sous le
    plancher est un défaut qu'on peut corriger en changeant une constante, maintenant,
    pendant qu'on a le contexte.
    """
    ref = _reference()
    connues = collections.Counter(ref["cles"])
    vues = collections.Counter()
    neuves = []
    for f in sorted(figures(), key=lambda x: x["delta_e"]):
        if f["delta_e"] >= PLANCHER:
            continue
        k = cle(f)
        vues[k] += 1
        if vues[k] > connues.get(k, 0):
            neuves.append(f"  {f['fichier']}:{f['ligne']}  ΔE {f['delta_e']} en "
                          f"{f['sous']}  {f['paire'][0]} ↔ {f['paire'][1]}")
    assert not neuves, (
        "figure(s) neuve(s) ou modifiée(s) sous le plancher d'attribution "
        f"({PLANCHER}) :\n" + "\n".join(neuves) +
        "\n\nDeux aires qu'un daltonien ne peut pas distinguer, c'est la définition "
        "d'une figure illisible — 8 % des hommes. Choisir des couleurs dans la même "
        "famille mais à des CLARTÉS séparées, ou ajouter un canal qui n'est pas la "
        "teinte (la valeur écrite sur la donnée, un motif de remplissage, une position "
        "distincte).\nSi la figure est légitime malgré sa mesure — parce qu'un autre "
        "canal l'attribue — régénérer la référence : "
        "`make figure-contrast-baseline`, en disant dans le commit POURQUOI l'œil "
        "tranche autrement que le chiffre.")


def test_the_baseline_only_shrinks() -> None:
    """Un cliquet : corriger une figure retire sa clé, rien ne doit en ajouter."""
    ref = _reference()
    assert ref["total"] <= 19, (
        f"la référence porte {ref['total']} figures sous le plancher, contre 19 le "
        "2026-09-18. Elle est un PLAFOND : elle descend quand une figure est corrigée, "
        "elle ne monte jamais. Un ajout est le raccourci que ce cliquet interdit.")


# ── Les deux mutations de la règle 20, en source SYNTHÉTIQUE ──────────────────
#
# Ni l'une ni l'autre ne touche le dépôt : elles construisent le fragment à la main et
# interrogent le prédicat. C'est ce qui permet de les rejouer à chaque exécution plutôt
# qu'une fois, à la main, le jour où le garde a été écrit.

_FAUX_NEGATIF = """
fig = go.Figure()
fig.add_trace(go.Bar(x=d.x, y=d.y, name="Bon", marker_color="#1DB954"))
fig.add_trace(go.Bar(x=d.x, y=d.z, name="Mauvais", marker_color="#FF6B6B"))
st.plotly_chart(fig)
"""

_FAUX_POSITIF = """
fig = make_subplots(rows=2, cols=1)
fig.add_trace(go.Bar(x=d.x, y=d.y, marker_color="#1DB954"), row=1, col=1)
fig.add_trace(go.Scatter(x=d.x, y=d.z, line=dict(color="#FF6B6B")), row=2, col=1)
st.plotly_chart(fig)
"""


def test_the_detector_sees_two_confusable_colours_in_one_panel() -> None:
    """FAUX NÉGATIF fabriqué : le vert et le rouge de ce dépôt, dans le MÊME panneau."""
    groupes = [g for g in _panneaux(_FAUX_NEGATIF) if len(g) >= 2]
    assert groupes, "le détecteur ne voit aucune paire dans le cas le plus simple"
    pires = [_pire_paire(g)[0] for g in groupes]
    assert min(pires) < PLANCHER, (
        f"ΔE minimal {min(pires):.1f} — le détecteur juge attribuables `#1DB954` et "
        "`#FF6B6B` côte à côte, ce qui est la paire dominante du parc et la raison "
        "d'être de ce garde.")


def test_the_detector_does_not_accuse_two_separate_panels() -> None:
    """FAUX POSITIF fabriqué : les MÊMES couleurs, sur deux panneaux distincts.

    C'est le cas réel de `_tab_algos.py:90`, et c'est l'écart entre le chiffre de 28 et
    celui de 19. Un garde qui accuse une figure correcte se fait désactiver.
    """
    groupes = [g for g in _panneaux(_FAUX_POSITIF) if len(g) >= 2]
    assert not groupes, (
        f"le détecteur oppose des couleurs de panneaux différents : {groupes}. "
        "`row=1` et `row=2` sont deux repères, aucun œil n'a à les attribuer l'un "
        "contre l'autre — et compter cela comme un défaut était l'erreur des deux "
        "premières mesures de cette grandeur.")


@pytest.mark.parametrize("hexa,neutre", [
    ("#ffffff", True), ("#eeeeee", True), ("#333333", True), ("#808080", True),
    ("#1db954", False), ("#ff6b6b", False), ("#457b9d", False),
])
def test_a_chrome_is_told_from_a_series_colour_by_chroma(hexa: str, neutre: bool) -> None:
    """Le tri chrome/série se fait sur la CHROMA, pas sur une liste de littéraux.

    Une liste (`#fff`, `#ffffff`, `white`, `#eee`…) serait le prédicat de FORME que la
    règle 20 interdit : elle rate le gris suivant qu'on écrira.
    """
    from tools.dev.figure_contrast_report import _neutre
    assert _neutre(hexa) is neutre
