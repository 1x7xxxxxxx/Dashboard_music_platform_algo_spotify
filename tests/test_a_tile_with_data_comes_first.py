"""Ce qui a des données passe devant — sans jamais casser une paire.

Type: Guard
Uses: src.dashboard.views.home_tiles
Persists in: nothing

La demande, et le défaut qu'elle nomme
---------------------------------------
« l'accueil montre en prio les plateformes qui ont des données ». Les six rangées de
tuiles étaient écrites à la main, dans un ordre fixe. Mesuré en production le
2026-09-22 : **Benken, le seul artiste bêta qui livre, n'a que SoundCloud et
YouTube** — et SoundCloud était en cinquième position, derrière quatre tirets.

Ce que ce garde tient, et qui est plus étroit qu'il n'y paraît
---------------------------------------------------------------
Trier par présence est facile. Trier SANS casser un voisinage voulu ne l'est pas, et
c'est la seule partie qui peut se perdre en silence : deux boîtes séparées restent
deux boîtes, la page se rend, aucun test de rendu ne bronche, et l'information que le
voisinage portait disparaît.

Deux paires existent, et chacune a sa raison ÉCRITE dans `home_tiles.py` :

    Apple + Shazam    même dépôt de CSV Apple, même nature de relevé — « les
                      voisiner laisse l'œil transporter la réserve de l'un sur
                      l'autre, au lieu de la répéter deux fois »
    Meta + Hypeddit   la chaîne que le produit raconte : « on dépense (Meta), les
                      gens cliquent (ici), le titre est écouté, l'algorithme le
                      reprend »

⚠️ Ce que ce garde NE tient PAS : l'ordre des trois BLOCS. Le total toutes
plateformes reste en tête et les trois portes algorithmiques en dernier — décision
datée du 2026-09-12, demandée mot pour mot. Le tri ne touche que les boîtes
plateformes.
"""
from __future__ import annotations

import pytest

from src.dashboard.views.home_tiles import agencer

#: Les paires dont la séparation perdrait une information. Les libellés sont ceux
#: que `st.metric` affiche — c'est par eux que les harnais de ce dépôt retrouvent
#: une boîte, jamais par index.
_PAIRES = (("🎎 Apple Music", "🎧 Shazam"), ("📊 Meta Ads", "📱 Hypeddit"))


def _rendre(totals: dict, side: dict | None = None, ig: int = 0) -> list[str]:
    """Les libellés des jauges, DANS L'ORDRE où elles sont rendues."""
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    # ⚠️ La RACINE en absolu, pas ".". `AppTest` écrit le script dans un répertoire
    # temporaire et l'exécute depuis là : un chemin relatif y désigne le mauvais
    # dossier, et l'import échoue sans que le message ne le dise.
    racine = str(Path(__file__).resolve().parents[1])
    src = (
        f"import sys; sys.path.insert(0, {racine!r})\n"
        "import streamlit as st\n"
        "from src.dashboard.views.home_tiles import render_tiles\n"
        f"render_tiles({totals!r}, sum(v or 0 for v in {totals!r}.values()), "
        f"{ig}, side={side or {}!r})\n"
    )
    at = AppTest.from_string(src)
    at.run(timeout=90)
    # ⚠️ `at.exception` rend une LISTE, vide quand tout va bien — jamais `None`.
    # Le premier jet testait `is None` et rougissait sur un rendu parfaitement sain.
    assert not at.exception, f"le rendu a levé : {at.exception}"
    return [m.label for m in at.metric]


# ══════════════════════════════════════════════════════════════════════════
# 1. L'AGENCEMENT — pur, éprouvé sur des valeurs
# ══════════════════════════════════════════════════════════════════════════

def test_a_pair_is_never_split_across_rows() -> None:
    """LE cas qu'un découpage naïf rate : une paire en position impaire.

    `[plat[i:i+2] for i in range(0, n, 2)]` rendrait `[a, b] [c, d] [e]` et
    couperait la paire `(b, c)`. `agencer` avance une unité d'une seule boîte pour
    combler, et la paire garde sa rangée.
    """
    rangees = agencer([["a"], ["b", "c"], ["d"], ["e", "f"]])
    plat = [x for r in rangees for x in r]
    for gauche, droite in (("b", "c"), ("e", "f")):
        i, j = plat.index(gauche), plat.index(droite)
        assert j == i + 1, f"la paire ({gauche}, {droite}) a été coupée : {rangees}"
        rangee = next(r for r in rangees if gauche in r)
        assert droite in rangee, (
            f"({gauche}, {droite}) sont adjacents mais sur DEUX rangées : {rangees}")


def test_a_row_is_left_short_rather_than_a_pair_broken() -> None:
    """L'ARBITRAGE, explicite : une demi-rangée vide coûte moins qu'une paire cassée.

    Une boîte seule suivie de deux paires ne peut pas remplir sa rangée sans en
    couper une. `agencer` la laisse seule.
    """
    rangees = agencer([["a"], ["b", "c"], ["d", "e"]])
    assert rangees[0] == ["a"], f"attendu une rangée courte, obtenu {rangees}"
    assert ["b", "c"] in rangees and ["d", "e"] in rangees


def test_nothing_is_lost_or_duplicated() -> None:
    """Une boîte qui disparaît est une information perdue, pas une simplification."""
    unites = [["a"], ["b", "c"], ["d"], ["e", "f"], ["g"]]
    attendu = [x for u in unites for x in u]
    obtenu = [x for r in agencer(unites) for x in r]
    assert sorted(obtenu) == sorted(attendu), (
        f"l'agencement a perdu ou dupliqué : {obtenu} contre {attendu}")


def test_the_layout_is_not_vacuous() -> None:
    """NON-VACUITÉ : une fonction qui rend une liste vide passerait tout le reste."""
    assert agencer([["a"], ["b"]]) == [["a", "b"]]
    assert agencer([]) == []


# ══════════════════════════════════════════════════════════════════════════
# 2. LE RENDU — l'ordre qu'un artiste voit vraiment
# ══════════════════════════════════════════════════════════════════════════

def test_the_only_platform_that_delivers_is_named_first() -> None:
    """LE CAS DE BENKEN, mesuré en production : SoundCloud seul.

    Avant le 2026-09-22 il sortait en cinquième position, derrière quatre tuiles à
    « — ». C'est l'écran d'accueil du seul artiste bêta qui ait des données.
    """
    libelles = _rendre({"soundcloud": 4200})
    assert libelles, "aucune jauge rendue — le harnais est cassé"
    assert libelles[0] == "☁️ SoundCloud", (
        f"SoundCloud livre et n'est pas en tête : {libelles}")


def test_a_full_tenant_keeps_the_declared_order() -> None:
    """LA RÉCIPROQUE. Le tri est STABLE : à présence égale, rien ne bouge.

    Sans elle, un tri instable réordonnerait l'écran d'un artiste installé à chaque
    rendu, sur un critère qui ne le concerne plus.
    """
    plein = {"spotify": 1000, "youtube": 900, "apple": 800, "soundcloud": 700}
    libelles = _rendre(plein, {"shazam_total": 1772, "meta_spend": 3088,
                               "hypeddit_ctr": 12.0}, ig=500)
    assert libelles[0] == "🎵 Spotify", (
        f"l'ordre de déclaration n'est pas préservé quand tout a des données : "
        f"{libelles}")


@pytest.mark.parametrize("totals,side,ig", [
    ({"soundcloud": 4200}, {}, 0),                                   # Benken
    ({}, {}, 0),                                                     # locataire vide
    ({"spotify": 10}, {"shazam_total": 5}, 0),                       # Shazam sans Apple
    ({"apple": 10}, {}, 0),                                          # Apple sans Shazam
    ({"spotify": 1, "youtube": 2, "apple": 3, "soundcloud": 4},
     {"shazam_total": 5, "meta_spend": 6, "hypeddit_ctr": 7.0}, 8),  # tout plein
])
def test_the_two_written_pairs_stay_adjacent(totals, side, ig) -> None:
    """Quel que soit l'état de la donnée, les deux paires restent collées.

    Le paramétrage porte les cas qui les SÉPARERAIENT : Shazam plein et Apple vide
    les met de part et d'autre de la frontière du tri, et c'est exactement là qu'une
    unité mal déclarée se romprait.
    """
    libelles = _rendre(totals, side, ig)
    for gauche, droite in _PAIRES:
        if gauche not in libelles or droite not in libelles:
            continue
        i, j = libelles.index(gauche), libelles.index(droite)
        assert j == i + 1, (
            f"« {gauche} » et « {droite} » ne sont plus voisins ({i} et {j}) dans "
            f"{libelles}. Leur voisinage est une décision écrite dans "
            "`home_tiles.py`, pas un hasard de place — les séparer perd ce que "
            "l'adjacence disait.")


def test_a_unit_counts_as_full_when_any_of_its_boxes_has_data() -> None:
    """Shazam vide ne doit pas faire descendre Apple qui livre.

    C'est le piège de l'unité : si la présence se jugeait sur la PREMIÈRE boîte, ou
    sur TOUTES, une paire à moitié pleine tomberait au mauvais endroit.
    """
    libelles = _rendre({"apple": 999}, {})       # Apple livre, Shazam non
    assert "🎎 Apple Music" in libelles
    place = libelles.index("🎎 Apple Music")
    vides = [libelles.index(x) for x in ("🎵 Spotify", "🎬 YouTube")
             if x in libelles]
    assert all(place < v for v in vides), (
        f"Apple a des données et passe derrière des tuiles vides : {libelles}")
