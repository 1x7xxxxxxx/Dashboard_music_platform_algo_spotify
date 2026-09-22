"""Le catalogue se classe sur ce qui bouge quand l'artiste agit.

Type: Test
Uses: src.dashboard.views.trigger_algo._catalogue (module pur)
Depends on: algo_knowledge.nearest_gate, machine_learning/models/v3/calibration.json
Persists in: nothing

⚠️ MESURÉ EN PRODUCTION LE 2026-09-22, sur les dix titres de l'artiste 1.

La page classait ses titres par probabilité, et par un `Score /20` qui étirait ces
probabilités en min-max sur une échelle de 20. Or les dix titres sont posés sur le
**plancher de la calibration Platt** : leurs scores bruts valent 0,0013 à 0,028 là
où il en faudrait 0,49 à 0,62 pour atteindre 50 % calibré. L'écart de `rr_probability`
entre le meilleur et le pire titre vaut **0,02 point**.

Le classement repose désormais sur l'**avancement vers la porte la plus proche**.
Mesuré sur les mêmes dix titres, il s'étale de **0,0075 à 0,9896** — une grandeur
qui sépare réellement, dans l'unité du geste (« il manque 160 ajouts playlist »),
et qui bouge quand l'artiste agit.

Ce que ce garde NE couvre PAS
------------------------------
(1) Il ne vérifie aucun rendu : qu'une figure trie autrement lui est invisible.
(2) Il ne juge pas les CIBLES de `ALGO_FEATURE_ZONES` — qu'un objectif de 165 saves
soit le bon est une question de modèle, pas de tri. (3) Il ne couvre pas le cas d'un
catalogue où les probabilités discrimineraient vraiment : ce jour-là il faudra
relire la décision, pas contourner le test.
"""
from __future__ import annotations

import math

import pytest

from src.dashboard.views.trigger_algo._catalogue import (
    BRUT_NEGLIGEABLE,
    construire,
    leviers_artiste,
    sur_le_plancher,
)

# Deux titres qui ne diffèrent QUE par leurs leviers de titre. Leurs probabilités
# sont identiques — c'est le cas qui distingue les deux règles de tri.
_PROCHE = {
    "song": "proche de la porte",
    "days_since_release": 900,
    "streams_28d": 89,
    "dw_probability": 0.0700, "rr_probability": 0.0655, "radio_probability": 0.1110,
    "features_json": {
        "SavesLast28Days_adj": 150, "PlaylistAddsLast28Days_adj": 160,
        "StreamsLast7Days": 0, "CurrentSpotifyFollowers_log": math.log1p(681),
        "HowManySongsHasThisArtistEverReleased": 11, "ReleaseConsistencyNum": 3,
        "DaysSinceRelease": 900,
    },
}
_LOIN = {
    **_PROCHE,
    "song": "loin de la porte",
    "streams_28d": 3,
    "features_json": {**_PROCHE["features_json"],
                      "SavesLast28Days_adj": 2, "PlaylistAddsLast28Days_adj": 1},
}


def test_the_frame_is_empty_but_shaped_when_there_is_nothing():
    """Un artiste tout neuf ne fait pas planter la page."""
    df = construire([])
    assert df.empty
    for c in ("song", "avancement", "gate_algo"):
        assert c in df.columns, f"colonne {c} absente d'une trame vide"


def test_the_closer_track_comes_first():
    """LE tri. Les deux titres ont la MÊME probabilité — seule la porte les sépare."""
    df = construire([_LOIN, _PROCHE])
    assert list(df["song"]) == ["proche de la porte", "loin de la porte"], (
        f"ordre rendu : {list(df['song'])}"
    )
    assert df["avancement"].iloc[0] > df["avancement"].iloc[1]


def test_probability_does_not_decide_the_order():
    """La réciproque, et c'est elle qui prouve que le tri a changé de nature.

    On donne au titre LOIN une probabilité bien meilleure. S'il remonte, c'est que
    la probabilité pèse encore quelque part.
    """
    loin_mais_mieux_note = {**_LOIN, "dw_probability": 0.95,
                            "rr_probability": 0.95, "radio_probability": 0.95}
    df = construire([loin_mais_mieux_note, _PROCHE])
    assert df["song"].iloc[0] == "proche de la porte", (
        "un titre mieux noté mais plus loin de sa porte est passé devant — le "
        "classement retient encore la probabilité"
    )


def test_a_track_with_no_gate_sinks_without_claiming_zero():
    """`None`, jamais 0 %. Une absence de levier n'est pas un travail non fait."""
    rien = {
        "song": "rien en zone malus", "days_since_release": 10, "streams_28d": 99999,
        "dw_probability": 0.07, "rr_probability": 0.065, "radio_probability": 0.11,
        "features_json": {
            "SavesLast28Days_adj": 9000, "PlaylistAddsLast28Days_adj": 9000,
            "StreamsLast7Days": 99999, "NonAlgoStreams28Days_log": math.log1p(99999),
            "nonalgo_known": 1, "ListenersStreamRatio28Days": 5.0,
            "CurrentSpotifyFollowers_log": math.log1p(99999),
            "HowManySongsHasThisArtistEverReleased": 300,
            "ReleaseConsistencyNum": 4, "DaysSinceRelease": 10,
            "IsThisSongOptedIntoSpotifyDiscoveryMode": 1, "discovery_mode_known": 1,
        },
    }
    df = construire([rien, _PROCHE])
    ligne = df[df["song"] == "rien en zone malus"].iloc[0]
    assert ligne["avancement"] is None or (isinstance(ligne["avancement"], float)
                                           and math.isnan(ligne["avancement"])), (
        f"avancement={ligne['avancement']!r} — un titre sans porte affiche un chiffre"
    )
    assert df["song"].iloc[-1] == "rien en zone malus", "il n'est pas descendu"


def test_artist_levers_are_listed_once_for_the_whole_catalogue():
    """Le « regrouper les panneaux » demandé, énoncé en une assertion.

    Trois titres, les mêmes leviers d'artiste : ils ne doivent apparaître qu'une
    fois. Les répéter par titre ferait passer un conseil pour trois.
    """
    df = construire([_PROCHE, _LOIN, {**_PROCHE, "song": "troisième"}])
    leviers = leviers_artiste(df)
    noms = [a["feature"] for a in leviers]
    assert len(noms) == len(set(noms)), f"leviers d'artiste répétés : {noms}"
    assert noms, "aucun levier d'artiste — le cas de test ne couvre rien"


def test_the_gate_names_a_unit_a_human_can_act_on():
    """« il manque 160 ajouts », pas « +0,004 de probabilité »."""
    df = construire([_PROCHE])
    ligne = df.iloc[0]
    assert ligne["gate_gap"] is not None and ligne["gate_unit"]
    assert ligne["gate_label"], "la porte ne nomme pas son levier"


@pytest.mark.parametrize("algo,proba", [("dw", 0.0700), ("rr", 0.0655), ("radio", 0.1110)])
def test_a_production_probability_is_flagged_as_the_floor(algo, proba):
    """Les trente probabilités de production sont au plancher — le marquage le dit."""
    assert sur_le_plancher(algo, proba), (
        f"{algo}={proba} n'est pas marqué « ≈ plancher » alors que son score brut "
        "est négligeable — l'artiste lira un chiffre qui distingue son titre"
    )


@pytest.mark.parametrize("algo", ["dw", "rr", "radio"])
def test_a_real_probability_is_not_flagged(algo):
    """La réciproque : un prédicat qui dirait « plancher » à tout ne garderait rien."""
    assert not sur_le_plancher(algo, 0.60), (
        f"{algo}=0,60 est marqué comme un plancher — le prédicat dit oui à tout"
    )


def test_the_floor_threshold_lives_in_raw_space():
    """Le seuil est sur le score BRUT, pas sur la probabilité affichée.

    C'est là qu'est le sens : 0,05 de brut est le douzième de ce qu'il faut pour
    atteindre 50 % calibré. Un seuil posé sur la valeur affichée serait arbitraire.
    """
    assert 0 < BRUT_NEGLIGEABLE < 0.10


def test_bad_input_does_not_raise():
    """`features_json` en texte, absent, ou illisible — la page rend quand même."""
    for feats in ('{"SavesLast28Days_adj": 2}', None, "", "pas du json", 42):
        df = construire([{"song": "x", "features_json": feats}])
        assert len(df) == 1, f"trame cassée sur features_json={feats!r}"
