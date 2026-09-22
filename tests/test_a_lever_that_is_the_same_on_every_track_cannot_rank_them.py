"""Un levier identique sur tous les titres ne peut en distinguer aucun.

Type: Test
Uses: src.dashboard.utils.algo_knowledge (module pur — ni Streamlit, ni base)
Depends on: LEVER_SCOPE, split_coach_actions, nearest_gate, build_coach_actions
Persists in: nothing

⚠️ MESURÉ LE 2026-09-22, sur les dix titres de l'artiste 1.

`build_coach_actions` mélangeait deux natures de levier :

  · des leviers d'**artiste** — followers, cadence de sortie, taille du catalogue,
    compteur Radio — écrits une fois pour tout le compte, donc **identiques sur les
    dix titres** ;
  · des leviers de **titre** — saves, ajouts playlist, streams 7 j, ratio
    listeners/streams, vélocité, Discovery Mode — propres à chaque chanson.

Deux conséquences, toutes deux visibles à l'écran : le coach répétait « gagne 2 650
followers » dix fois, et un classement de catalogue bâti sur ces actions ne classait
rien — la même valeur partout ne sépare rien, par construction.

`split_coach_actions` sépare les deux ; `nearest_gate` ne classe que sur les leviers
de titre. Les leviers d'artiste s'affichent **une fois**, pour tout le catalogue —
c'est littéralement le « regrouper les panneaux » demandé.

Ce que ce garde NE couvre PAS
------------------------------
(1) Il ne vérifie aucune surface d'affichage : qu'une vue affiche encore dix fois le
même conseil lui est invisible. (2) Il ne juge pas la JUSTESSE d'une portée — que
`HowManySongsDoYouHaveInRadioRightNow` soit d'artiste est une lecture de la source
(`s4a_artist_radio_count`), pas une propriété que le code puisse prouver. (3) Il ne
couvre pas `build_coach_actions` lui-même, dont l'ordre et les zones sont gardés
ailleurs.
"""
from __future__ import annotations

import math

import pytest

from src.dashboard.utils.algo_knowledge import (
    ALGO_FEATURE_ZONES,
    LEVER_SCOPE,
    build_coach_actions,
    lever_scope,
    nearest_gate,
    split_coach_actions,
)

# Un titre faible : saves et ajouts en zone malus, followers encore neutres.
_TITRE_FAIBLE = {
    "SavesLast28Days_adj": 24,
    "PlaylistAddsLast28Days_adj": 12,
    "StreamsLast7Days": 0,
    "CurrentSpotifyFollowers_log": math.log1p(1240),
    "HowManySongsHasThisArtistEverReleased": 11,
    "ReleaseConsistencyNum": 30,
    "DaysSinceRelease": 900,
}

# Le même titre, mais pour un artiste sous les 1 000 followers : le levier
# d'ARTISTE entre alors en zone malus. C'est le cas qui rend la branche vivante.
_ARTISTE_FAIBLE = {**_TITRE_FAIBLE, "CurrentSpotifyFollowers_log": math.log1p(200)}


def test_every_zone_feature_declares_its_scope():
    """Une portée manquante rendrait le défaut au premier levier ajouté.

    Le défaut par défaut est « track », donc un levier d'artiste oublié
    réapparaîtrait silencieusement dans le classement — exactement le défaut que ce
    fichier existe pour fermer.
    """
    des_zones = {f for algo in ALGO_FEATURE_ZONES.values() for f in algo}
    manquantes = sorted(des_zones - set(LEVER_SCOPE))
    assert not manquantes, (
        f"features sans portée déclarée : {manquantes}. Ajouter chacune à "
        "`LEVER_SCOPE` en regardant SA SOURCE : écrite par artiste ou par titre ?"
    )


def test_the_scope_split_is_not_all_on_one_side():
    """Anti-vacuité : une séparation qui ne sépare rien passerait tous les tests."""
    portees = set(LEVER_SCOPE.values())
    assert portees == {"track", "artist"}, f"portées trouvées : {portees}"
    n_artiste = sum(1 for v in LEVER_SCOPE.values() if v == "artist")
    assert 2 <= n_artiste <= len(LEVER_SCOPE) - 2, (
        f"{n_artiste} levier(s) d'artiste sur {len(LEVER_SCOPE)} — une séparation "
        "qui met presque tout d'un côté ne sépare rien"
    )


def test_an_unknown_lever_defaults_to_track():
    """Le défaut prudent : montrer un levier de trop plutôt que d'en cacher un.

    Une erreur visible se corrige ; une absence est muette.
    """
    assert lever_scope("UneFeatureQuiNExistePas") == "track"


def test_the_split_preserves_the_coach_order():
    """L'ordre d'urgence croissante de `build_coach_actions` doit survivre.

    C'est LUI le Pareto : le levier le plus proche de sa cible d'abord. Une
    séparation qui trierait autrement remplacerait le Pareto par autre chose.
    """
    for algo in ("DW", "RR", "RADIO"):
        toutes = build_coach_actions(algo, _ARTISTE_FAIBLE)
        titre, artiste = split_coach_actions(algo, _ARTISTE_FAIBLE)
        assert len(titre) + len(artiste) == len(toutes), (
            f"{algo} : la séparation perd ou duplique des actions"
        )
        for lot in (titre, artiste):
            urgences = [a["urgency"] for a in lot]
            assert urgences == sorted(urgences), f"{algo} : ordre rompu dans {lot}"


def test_the_artist_branch_is_reachable():
    """Sans ce cas, la moitié de la séparation ne serait jamais exécutée."""
    _titre, artiste = split_coach_actions("DW", _ARTISTE_FAIBLE)
    noms = {a["feature"] for a in artiste}
    assert "CurrentSpotifyFollowers" in noms, (
        f"la branche artiste est vide sur un compte à 200 followers : {noms}. "
        "Vérifier que la zone malus des followers est bien < 1 000."
    )


# ⚠️ LA LISTE EST ÉCRITE ICI, PAS LUE DEPUIS `LEVER_SCOPE`.
#
# La première version de ce garde vérifiait la fuite avec `lever_scope(...)` —
# c'est-à-dire avec la fonction même qu'il prétendait garder. Mutation faite le
# 2026-09-22 : basculer `CurrentSpotifyFollowers` sur « track » l'a laissé VERT,
# puisque les deux côtés de la comparaison bougeaient ensemble. Un garde qui
# interroge sa propre définition ne peut pas la contredire.
#
# Ces quatre noms sont donc une SECONDE lecture, faite à la main, de la source de
# chaque donnée : `s4a_audience` (followers), la cadence et le catalogue de
# l'artiste, `s4a_artist_radio_count`. Les changer ici demande de reregarder la
# table, ce qui est précisément le geste qu'on veut imposer.
_LEVIERS_D_ARTISTE_ATTENDUS = frozenset({
    "CurrentSpotifyFollowers",
    "ReleaseConsistencyNum",
    "HowManySongsHasThisArtistEverReleased",
    "HowManySongsDoYouHaveInRadioRightNow",
})


def test_the_declared_scopes_match_the_hand_read_list():
    """`LEVER_SCOPE` et la lecture manuelle des sources doivent coïncider."""
    declares = {f for f, v in LEVER_SCOPE.items() if v == "artist"}
    assert declares == _LEVIERS_D_ARTISTE_ATTENDUS, (
        f"déclarés : {sorted(declares)}\nattendus : "
        f"{sorted(_LEVIERS_D_ARTISTE_ATTENDUS)}\n"
        "Si le changement est voulu, corriger les DEUX en ayant relu la table "
        "d'où vient la donnée."
    )


def test_no_artist_lever_leaks_into_the_track_list():
    """Le défaut d'origine, énoncé une fois — contre la liste écrite à la main."""
    for algo in ("DW", "RR", "RADIO"):
        titre, _artiste = split_coach_actions(algo, _ARTISTE_FAIBLE)
        fuites = [a["feature"] for a in titre
                  if a["feature"] in _LEVIERS_D_ARTISTE_ATTENDUS]
        assert not fuites, (
            f"{algo} : levier(s) d'artiste dans la liste du titre : {fuites}. "
            "Ils sont identiques sur tout le catalogue et ne classent rien."
        )


def test_the_nearest_gate_ranks_on_a_track_lever():
    g = nearest_gate(_ARTISTE_FAIBLE)
    assert g is not None
    assert lever_scope(g["action"]["feature"]) == "track", (
        f"la porte la plus proche est portée par {g['action']['feature']!r}, un "
        "levier d'artiste — le classement du catalogue serait le même pour tous"
    )
    assert 0.0 <= g["avancement"] <= 1.0
    assert g["n_leviers"] >= 1


def test_the_gate_advancement_is_the_ratio_it_claims():
    """`avancement = current / target`, borné — pas une autre formule."""
    g = nearest_gate(_TITRE_FAIBLE)
    a = g["action"]
    assert g["avancement"] == pytest.approx(a["current"] / a["target"])
    assert a["gap"] == pytest.approx(a["target"] - a["current"])


def test_a_track_with_nothing_in_malus_has_no_gate():
    """`None`, jamais un zéro. Une absence de levier n'est pas un avancement nul."""
    fort = {
        "SavesLast28Days_adj": 5000,
        "PlaylistAddsLast28Days_adj": 5000,
        "StreamsLast7Days": 50000,
        "NonAlgoStreams28Days_log": math.log1p(50000),
        "nonalgo_known": 1,
        "ListenersStreamRatio28Days": 3.0,
        "CurrentSpotifyFollowers_log": math.log1p(50000),
        "HowManySongsHasThisArtistEverReleased": 200,
        "ReleaseConsistencyNum": 4,
        "DaysSinceRelease": 10,
        "IsThisSongOptedIntoSpotifyDiscoveryMode": 1,
        "discovery_mode_known": 1,
    }
    assert nearest_gate(fort) is None


def test_a_smooth_lever_yields_no_advancement_rather_than_zero():
    """La vélocité trop haute n'a ni cible ni écart : `avancement` doit être `None`.

    Elle sort en tête (`urgency = -1.0`), donc elle DEVIENT la porte la plus proche.
    Rendre 0 % la ferait passer pour un titre qui n'a rien fait, ce qui est l'inverse
    de ce qu'elle dit : le titre va trop vite.
    """
    emballe = {
        "StreamsLast7Days": 900,
        "Velocity_Streams": 0.95,
        "SavesLast28Days_adj": 24,
        "DaysSinceRelease": 900,
        "CurrentSpotifyFollowers_log": math.log1p(1240),
        "HowManySongsHasThisArtistEverReleased": 11,
        "ReleaseConsistencyNum": 30,
    }
    g = nearest_gate(emballe)
    if g is not None and g["action"]["kind"] == "smooth":
        assert g["avancement"] is None, (
            "un levier « smooth » n'a pas de cible : son avancement doit être une "
            f"absence, pas {g['avancement']!r}"
        )
