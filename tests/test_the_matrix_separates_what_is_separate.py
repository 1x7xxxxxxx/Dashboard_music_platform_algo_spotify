"""La matrice d'état : quatre questions distinctes, et deux sources pour Spotify.

Type: Test
Uses: artist_readiness (pur), status_matrix._shape_cell
Depends on: src/utils/artist_readiness.py, src/dashboard/utils/status_matrix.py,
    src/utils/freshness_monitor.py
Persists in: nothing

Trois demandes du 2026-09-04, une même racine : **la matrice fondait des choses
différentes dans une seule case**.

  1. « séparer spotify de spotify 4 artist qui sont 2 process différents (csv et
     l'autre API) » — une ligne unique montrait le MEILLEUR des deux sources. Un
     artiste dont l'API remonte et qui n'a jamais déposé de CSV lisait 🟢, sans
     savoir que la moitié CSV n'existe pas ; l'inverse aussi. Les deux situations
     appellent des gestes opposés.
  2. « on a meta ads et instagram séparé mais quand on configure meta ads on a accès
     à insta ??? » — les deux SONT deux plateformes (deux identités, deux collectes,
     deux pannes possibles), mais rien ne disait qu'elles se saisissent au même
     endroit.
  3. « rajoute un step saisie des identifiants qui n'est pas le même que configuré
     car on peut l'avoir mal renseigné » — « Configuré » ne mesurait que « une valeur
     est là ». Une valeur peut être là ET fausse.

Ce que ce fichier fige : la SÉPARATION, pas les libellés. Refondre deux sources en
une, ou reperdre le « où ça se configure », redevient rouge.
"""
from __future__ import annotations

import pytest

from src.dashboard.utils.status_matrix import _shape_cell
from src.utils.artist_readiness import _PLATFORMS
from src.utils.freshness_monitor import SOURCES_FOR_PLATFORM, sources_for


# ── 1. Spotify a deux sources, et elles restent distinctes ───────────────────

def test_spotify_still_has_two_provable_sources():
    """L'API et le CSV S4A prouvent Spotify chacun de leur côté."""
    assert set(sources_for("spotify")) == {"Spotify API", "Spotify S4A"}, (
        "Spotify n'a plus deux sources : la ligne unique redeviendrait le meilleur "
        "des deux, et l'artiste ne saurait plus laquelle des deux marche."
    )


def test_every_platform_declares_at_least_one_source():
    """Une plateforme sans source ne peut jamais passer au vert.

    Non-vacuité : sans cette assertion, vider `SOURCES_FOR_PLATFORM` ferait passer
    le test ci-dessus au rouge mais laisserait les autres verts sur une matrice qui
    ne mesure plus rien.
    """
    for p in _PLATFORMS:
        assert sources_for(p["key"]), (
            f"{p['key']} n'a aucune source de fraîcheur : sa colonne « Données » ne "
            "peut structurellement pas devenir verte."
        )


def test_only_spotify_needs_the_two_line_display():
    """Le rendu à deux lignes se déclenche sur `len(by_source) > 1`, pas sur un nom.

    Si une deuxième plateforme gagne une source demain, elle est détaillée sans
    qu'on touche à la vue — et ce test dit alors laquelle, plutôt que d'échouer.
    """
    multi = [k for k, v in SOURCES_FOR_PLATFORM.items() if len(v) > 1]
    assert multi == ["spotify"], (
        f"plateformes à sources multiples : {multi}. Le rendu détaillé les couvre "
        "toutes ; ce test existe pour que l'ajout soit VU, pas pour l'interdire."
    )


# ── 2. Où chaque plateforme se configure ─────────────────────────────────────

def test_every_platform_says_where_it_is_configured():
    for p in _PLATFORMS:
        assert p.get("where"), (
            f"{p['key']} ne dit pas où il se règle. C'est la ligne qui répond à "
            "« pourquoi Meta Ads et Instagram sont-ils séparés ici alors que je les "
            "saisis au même endroit ? »"
        )


def test_meta_and_instagram_point_at_the_same_tab():
    """Séparées dans la matrice, saisies au même endroit — et la matrice le dit."""
    where = {p["key"]: p["where"] for p in _PLATFORMS}
    assert where["meta"] == where["instagram"], (
        "Meta Ads et Instagram ne nomment plus le même onglet de saisie, alors "
        "qu'`_registry.PLATFORMS` n'en a qu'un pour les deux."
    )
    assert "Meta" in where["meta"] and "Instagram" in where["meta"], (
        f"{where['meta']!r} ne nomme pas l'onglet tel qu'il s'appelle "
        "(« Meta / Instagram »)"
    )


def test_they_remain_two_rows():
    """Les fondre perdrait l'information qui compte.

    Instagram peut être muet pendant que Meta Ads répond : ce sont deux identités,
    deux DAGs et deux pannes. « Simplifier » veut dire expliquer, pas fusionner.
    """
    keys = [p["key"] for p in _PLATFORMS]
    assert "meta" in keys and "instagram" in keys, (
        "Meta et Instagram ont été fondus en une ligne : une panne Instagram "
        "deviendrait invisible tant que Meta Ads répond."
    )


# ── 3. « Saisi » et « Format » ne posent pas la même question ────────────────

@pytest.mark.parametrize("platform,value,expect", [
    ("spotify", "3TVXtAsR1Inumwj472S9r4", "green"),
    ("spotify", "https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4", "red"),
    ("meta", "act_123456789", "green"),
    ("meta", "https://adsmanager.facebook.com/?act=123", "red"),
    ("youtube", "UC_x5XG1OV2P6uZZ5FSM9Ttw", "green"),
    ("youtube", "@monpseudo", "red"),
])
def test_shape_tells_a_well_formed_value_from_a_pasted_one(platform, value, expect):
    """Une valeur collée avec du texte autour est SAISIE mais mal formée.

    C'est exactement la distinction demandée : la colonne « Saisi » dirait ✅ pour
    les six cas ci-dessous. Seule « Format » sépare les trois qui marcheront des
    trois qui ne marcheront jamais.
    """
    row = {"key": platform, "status": "no_data"}
    state, _glyph, _tip = _shape_cell(row, {platform: value})
    assert state == expect, f"{platform} / {value!r} → {state}, attendu {expect}"


def test_shape_is_neutral_when_nothing_was_entered():
    """Rien à vérifier n'est ni vert ni rouge — c'est gris.

    Un ✖ sur une plateforme qu'on n'a pas touchée enverrait corriger une valeur qui
    n'existe pas ; un ✅ dirait qu'elle est bonne.
    """
    state, glyph, _ = _shape_cell({"key": "spotify", "status": "todo"}, {})
    assert state == "grey" and glyph == "—"


def test_shape_never_greens_a_value_it_cannot_read():
    """Saisi mais illisible ici ⇒ « ? », jamais ✅.

    C'est la règle qui gouverne déjà la colonne « Répond » : une chose non mesurée ne
    se dessine pas comme une chose mesurée et réussie.
    """
    state, glyph, _ = _shape_cell({"key": "spotify", "status": "no_data"}, {})
    assert state == "grey" and glyph == "?"
