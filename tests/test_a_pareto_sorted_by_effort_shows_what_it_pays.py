"""Un Pareto trié par effort doit dire ce que chaque levier rapporte.

Type: Test
Uses: src.dashboard.views.trigger_algo._pareto, machine_learning/models/v3
Depends on: algo_knowledge.ALGO_FEATURE_ZONES, ml_inference.local_sensitivity
Persists in: nothing

⚠️ LE FAIT QUI JUSTIFIE LA COLONNE « CE QUE ÇA RAPPORTE » — mesuré le 2026-09-22.

`build_coach_actions` trie par `urgency = |écart| / |cible|` croissant : le levier le
plus proche de sa cible d'abord. C'est un Pareto d'**effort**, et c'est le bon tri
par défaut — on veut le prochain pas le moins cher.

Mais l'effort n'est pas l'impact. Sur « Kimono à semelle de fer - Remix », en
production :

    levier #1  ajouts playlist   il manque   165   →  +0,06 point  (+0,02 €)
    levier #3  streams 7 jours   il manque 2 000   →  +2,04 points (+0,76 €)

Le levier le plus proche est **trente fois moins rentable** que le plus lointain. Un
tableau qui n'afficherait que l'ordre laisserait donc l'artiste travailler le levier
le moins utile en croyant faire le plus malin.

⚠️ ET UN DÉFAUT TROUVÉ EN EXÉCUTANT, PAS EN RELISANT
-----------------------------------------------------
`ALGO_FEATURE_ZONES` nomme un levier `SavesLast28Days` ; la colonne du modèle
s'appelle `SavesLast28Days_adj`, et `StreamsLast7Days` devient `StreamsLast7Days_log`.
`local_sensitivity` rejette **silencieusement** tout nom qui n'est pas le sien
(`feature not in FEATURE_COLUMNS` → `None`). Passer l'identifiant de zone rendait
donc **zéro euro sur tous les leviers, sans le moindre message** — une colonne
entièrement vide qui se lisait comme « aucun levier ne rapporte ».

Ce que ce garde NE couvre PAS
------------------------------
(1) La JUSTESSE du Δprobabilité — c'est le modèle qui le produit, pas cette
fonction. (2) Les valeurs de `trigger_value` (la cohorte), gardées ailleurs. (3) Le
rendu : qu'un tableau cache la colonne lui est invisible.
"""
from __future__ import annotations

import math

import pytest

from src.dashboard.utils.algo_knowledge import ALGO_FEATURE_ZONES
from src.dashboard.views.trigger_algo._pareto import (
    LEVIERS_CHIFFRES,
    _colonne_modele,
    pareto,
)

# Un titre réel de la production : tout est en zone malus sauf l'âge.
_FEATS = {
    "SavesLast28Days_adj": 0.0,
    "PlaylistAddsLast28Days_adj": 10.0,
    "StreamsLast7Days_log": 0.0,
    "NonAlgoStreams28Days_log": math.log1p(19.0),
    "nonalgo_known": 1,
    "ListenersStreamRatio28Days_adj": 1.2,
    "CurrentSpotifyFollowers_log": math.log1p(681),
    "HowManySongsHasThisArtistEverReleased": 11,
    "HowManySongsDoYouHaveInRadioRightNow": 0,
    "radio_known": 1,
    "ReleaseConsistencyNum": 3,
    "DaysSinceRelease": 1032,
    "IsThisSongOptedIntoSpotifyDiscoveryMode": 0,
    "discovery_mode_known": 1,
}


def test_the_model_column_is_not_the_zone_id():
    """Le défaut qui rendait la colonne euro entièrement vide, en silence."""
    from src.utils.ml_inference import FEATURE_COLUMNS

    for fid in ("SavesLast28Days", "PlaylistAddsLast28Days", "StreamsLast7Days",
                "ListenersStreamRatio28Days"):
        colonne = _colonne_modele("DW", fid)
        assert colonne in FEATURE_COLUMNS, (
            f"{fid} → {colonne!r} n'est pas une colonne du modèle : "
            "`local_sensitivity` rendra `None` sans rien dire, et tous les euros "
            "du tableau seront vides"
        )


def test_at_least_one_zone_id_really_differs_from_its_column():
    """Anti-vacuité : si les deux noms coïncidaient, le test précédent ne prouverait rien."""
    differents = [fid for fid in ALGO_FEATURE_ZONES["DW"]
                  if _colonne_modele("DW", fid) != fid]
    assert differents, (
        "aucun identifiant de zone ne diffère de sa colonne modèle — la "
        "correspondance ne sert à rien, ou elle a cessé de fonctionner"
    )


def test_the_pareto_is_ordered_by_effort():
    """Le tri par défaut, celui de `build_coach_actions` : le moins loin d'abord."""
    plan = pareto(_FEATS, valeur_porte=32.81)
    assert plan is not None
    urgences = [a["urgency"] for a in plan["leviers"]]
    assert urgences == sorted(urgences), f"ordre rompu : {urgences}"


def test_a_smooth_lever_never_becomes_row_one():
    """Il n'a ni cible ni écart : en ligne 1 il donnerait un tableau sans chiffre."""
    emballe = {**_FEATS, "Velocity_Streams": 0.95, "StreamsLast7Days_log": math.log1p(900)}
    plan = pareto(emballe, valeur_porte=32.81)
    assert plan is not None
    assert all(a.get("kind") != "smooth" for a in plan["leviers"]), (
        "un levier « smooth » est resté dans le tableau"
    )
    if plan["smooth"]:
        assert plan["smooth"]["target"] is None


def test_only_the_first_levers_are_priced():
    """Chaque euro coûte 25 appels au modèle — on en chiffre trois, pas quinze."""
    plan = pareto(_FEATS, valeur_porte=32.81)
    chiffres = [a for a in plan["leviers"] if a["delta_proba"] is not None]
    assert len(chiffres) <= LEVIERS_CHIFFRES, (
        f"{len(chiffres)} leviers chiffrés pour un plafond de {LEVIERS_CHIFFRES}"
    )
    for a in plan["leviers"][LEVIERS_CHIFFRES:]:
        assert a["valeur_eur"] is None, (
            "un levier au-delà du plafond porte une valeur — une absence déclarée "
            "vaut mieux qu'un zéro qui se lit « ça ne rapporte rien »"
        )


def test_the_money_column_is_actually_filled():
    """LE test qui aurait attrapé le défaut de nom de colonne.

    Sans lui, un Pareto qui rend `None` partout passe tous les autres tests : il est
    ordonné, il n'a pas de smooth en tête, et il respecte le plafond.
    """
    plan = pareto(_FEATS, valeur_porte=32.81)
    chiffres = [a for a in plan["leviers"] if a["valeur_eur"] is not None]
    assert chiffres, (
        "aucun levier n'a de valeur en euros. C'est exactement ce que produisait le "
        "défaut de nom de colonne : `local_sensitivity` rejette en silence un nom "
        "qu'il ne connaît pas."
    )


def test_a_gate_with_no_value_yields_no_euros_but_still_ranks():
    """Sans taux €/écoute, le Pareto existe quand même — sans sa colonne d'argent."""
    plan = pareto(_FEATS, valeur_porte=None)
    assert plan and plan["leviers"], "le plan disparaît quand l'argent manque"
    assert all(a["valeur_eur"] is None for a in plan["leviers"])


def test_nothing_in_malus_yields_no_plan():
    """`None`, pas un plan vide : rien à faire n'est pas la même chose que rien su."""
    parfait = {
        "SavesLast28Days_adj": 9000, "PlaylistAddsLast28Days_adj": 9000,
        "StreamsLast7Days_log": math.log1p(99999),
        "NonAlgoStreams28Days_log": math.log1p(99999), "nonalgo_known": 1,
        "ListenersStreamRatio28Days_adj": 5.0,
        "CurrentSpotifyFollowers_log": math.log1p(99999),
        "HowManySongsHasThisArtistEverReleased": 300,
        "HowManySongsDoYouHaveInRadioRightNow": 40, "radio_known": 1,
        "ReleaseConsistencyNum": 4, "DaysSinceRelease": 10,
        "IsThisSongOptedIntoSpotifyDiscoveryMode": 1, "discovery_mode_known": 1,
    }
    assert pareto(parfait, valeur_porte=32.81) is None


@pytest.mark.parametrize("feats", [{}, None])
def test_no_features_does_not_raise(feats):
    assert pareto(feats or {}, valeur_porte=32.81) is None
