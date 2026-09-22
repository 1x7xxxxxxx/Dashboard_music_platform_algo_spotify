"""Un réglage testé une fois n'est pas un enseignement.

Type: Test
Uses: src.dashboard.views.trigger_algo._reglages (module pur)
Depends on: rien — ni base, ni Streamlit
Persists in: nothing

⚠️ MESURÉ EN PRODUCTION LE 2026-09-22, et c'est ce qui rend ce garde nécessaire.

Le panneau de réglages compare les paramètres de campagne sur leur coût par clic
réel. Sur l'artiste 1, les effectifs vont de **1 annonce à 84** et les dépenses de
**13 € à 5 198 €** :

    LISTEN_NOW      84 ads   5 198 €   0,1177 €/clic
    (aucun)         25 ads     897 €   0,2117 €/clic
    LEARN_MORE      22 ads      60 €   0,2215 €/clic
    MESSAGE_PAGE     1 ad       13 €   1,4489 €/clic

    OUTCOME_ENGAGEMENT  17 camp.  6 078 €   0,1256 €/clic
    CONVERSIONS          3 camp.     61 €   0,2279 €/clic
    VIDEO_VIEWS          2 camp.     30 €   2,7164 €/clic

Classer ces lignes sans leur effectif produirait un conseil — « ne fais jamais de
vidéo », « n'utilise jamais MESSAGE_PAGE » — que la donnée ne porte pas : deux
campagnes et trente euros ne départagent rien.

Deux règles, et elles sont le sujet du fichier :
  1. une ligne trop mince **ne peut jamais prendre la tête** d'un classement, même
     si elle affiche le meilleur coût ;
  2. une recommandation exige **deux** lignes fiables — un « meilleur » sans rival
     mesuré n'est pas un enseignement, c'est la seule chose qu'on ait essayée.

C'est la même discipline que R147 sur les cohortes d'essai et que le plancher de
calibration : un chiffre sur une population trop petite n'est pas un résultat.

Ce que ce garde NE couvre PAS
------------------------------
(1) Les SEUILS eux-mêmes (5 annonces, 100 €) : ce sont des bornes de lecture
calibrées sur ce catalogue, pas des vérités. (2) La causalité — qu'un appel à
l'action moins cher soit la CAUSE du coût, et non le symptôme d'une audience
différente, aucune donnée ici ne le dit. (3) Le rendu : qu'une vue cache la colonne
d'effectif lui est invisible.
"""
from __future__ import annotations

import pytest

from src.dashboard.views.trigger_algo._reglages import (
    MIN_ADS,
    MIN_DEPENSE,
    budget_pour_streams,
    classer,
    recommandation,
)

# La production du 2026-09-22, axe « appel à l'action ».
_PROD_CTA = [
    {"valeur": "LISTEN_NOW", "ads": 84, "depense": 5198.42,
     "clics": 44168, "impressions": 3317976},
    {"valeur": None, "ads": 25, "depense": 897.44, "clics": 4240, "impressions": 268668},
    {"valeur": "LEARN_MORE", "ads": 22, "depense": 59.80, "clics": 270, "impressions": 14546},
    {"valeur": "MESSAGE_PAGE", "ads": 1, "depense": 13.04, "clics": 9, "impressions": 1102},
]


def test_the_production_shape_is_reproduced():
    df = classer(_PROD_CTA, "Appel à l'action")
    assert len(df) == 4
    ligne = df[df["valeur"] == "LISTEN_NOW"].iloc[0]
    assert ligne["cpc"] == pytest.approx(5198.42 / 44168, rel=1e-6)
    assert ligne["fiable"]


def test_a_thin_row_never_takes_the_lead():
    """LA règle. Une ligne à une annonce affichant le MEILLEUR coût reste derrière.

    Sans ce cas, le tri par coût seul mettrait un coup de chance en tête du tableau,
    là où il se lit « voilà ce qu'il faut faire ».
    """
    avec_coup_de_chance = _PROD_CTA + [
        {"valeur": "UN_SEUL_ESSAI", "ads": 1, "depense": 4.0,
         "clics": 400, "impressions": 5000},           # 0,01 €/clic, imbattable
    ]
    df = classer(avec_coup_de_chance, "Appel à l'action")
    assert df.iloc[0]["valeur"] != "UN_SEUL_ESSAI", (
        "une ligne à une annonce a pris la tête du classement"
    )
    chanceux = df[df["valeur"] == "UN_SEUL_ESSAI"].iloc[0]
    assert not chanceux["fiable"]
    assert chanceux["cpc"] < df.iloc[0]["cpc"], (
        "le cas de test ne prouve rien : la ligne mince n'est pas la moins chère"
    )


def test_a_recommendation_needs_two_reliable_rows():
    """Un « meilleur » sans rival mesuré n'est pas un enseignement."""
    un_seul = [
        {"valeur": "SEUL", "ads": 40, "depense": 900.0, "clics": 9000, "impressions": 500000},
        {"valeur": "TROP_MINCE", "ads": 2, "depense": 8.0, "clics": 20, "impressions": 900},
    ]
    assert recommandation(classer(un_seul, "Objectif")) is None


def test_the_production_objective_axis_yields_no_recommendation():
    """Le cas réel : un seul objectif dépasse le plancher de dépense.

    `OUTCOME_ENGAGEMENT` pèse 6 078 € ; `CONVERSIONS` 61 € et `VIDEO_VIEWS` 30 €
    sont tous deux sous les 100 €. Le panneau doit donc se TAIRE sur cet axe, et
    c'est le comportement correct — pas un trou.
    """
    objectifs = [
        {"valeur": "OUTCOME_ENGAGEMENT", "ads": 17, "depense": 6078.20,
         "clics": 48392, "impressions": 3584000},
        {"valeur": "CONVERSIONS", "ads": 3, "depense": 60.62,
         "clics": 266, "impressions": 26000},
        {"valeur": "VIDEO_VIEWS", "ads": 2, "depense": 29.88,
         "clics": 11, "impressions": 3400},
    ]
    assert recommandation(classer(objectifs, "Objectif")) is None


def test_a_real_recommendation_carries_its_evidence():
    """Quand elle existe, elle dit sur quoi elle repose."""
    reco = recommandation(classer(_PROD_CTA, "Appel à l'action"))
    assert reco is not None
    assert reco["retenir"] == "LISTEN_NOW"
    assert reco["sur_ads"] == 84 and reco["sur_depense"] == pytest.approx(5198.42)
    assert reco["facteur"] > 1.0, "un facteur ≤ 1 dirait que le meilleur est le pire"


def test_the_thresholds_are_not_vacuous():
    """Des bornes à zéro laisseraient tout passer et le fichier ne garderait rien."""
    assert MIN_ADS >= 2 and MIN_DEPENSE > 0


def test_an_empty_axis_yields_a_shaped_frame():
    df = classer([], "Objectif")
    assert df.empty
    for c in ("valeur", "ads", "cpc", "fiable"):
        assert c in df.columns


def test_a_row_with_no_click_has_no_cost_rather_than_zero():
    """Une absence de clic ne fait pas un coût nul — elle fait un coût inconnu."""
    df = classer([{"valeur": "JAMAIS_CLIQUÉ", "ads": 9, "depense": 300.0,
                   "clics": 0, "impressions": 90000}], "Créative")
    assert df.iloc[0]["cpc"] is None


@pytest.mark.parametrize("manque,cout,attendu", [
    (1993, 0.0165, 1993 * 0.0165),
    (0, 0.0165, 0.0),
    (1993, None, None),
    (1993, 0.0, None),
    (None, 0.0165, None),
])
def test_the_trigger_budget_is_a_plain_product_or_nothing(manque, cout, attendu):
    """Pas de coût par écoute ⇒ pas de budget. Jamais un zéro qui se lit « gratuit »."""
    got = budget_pour_streams(manque, cout)
    if attendu is None:
        assert got is None
    else:
        assert got == pytest.approx(attendu)
