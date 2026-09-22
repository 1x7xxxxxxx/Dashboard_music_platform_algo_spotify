"""Un taux de conversion ne s'affiche pas sur trois essais.

Type: Sub
Uses: src.dashboard.views.alerts._trial_cohorts, _essais_avant_de_douter
Depends on: pandas
Persists in: nothing

R147, mesurée en production le 2026-09-22 : **cinq essais accordés, trois arrivés au
jour 30, zéro conversion**. La tentation est d'écrire « 0 % de conversion » — et ce
serait une invention : sous le repère de 15 % de *Lean Analytics* (essai SANS carte
bancaire), observer zéro sur trois a une probabilité de 0,85³ = **61 %**. C'est
l'issue la plus probable, pas un signal.

Classe : `a-rate-published-on-a-population-that-cannot-produce-one`. Elle est la
sœur de `anchor-a-number-to-its-population`, déjà payée sur ce dépôt.

⚠️ Ce que ce garde couvre : la DÉCISION d'afficher un taux, et l'effectif qui la
déclenche. Ce qu'il NE couvre pas : la mise en forme du message, et surtout tout
AUTRE taux de l'app calculé sur un petit dénominateur — un CPR sur deux conversions,
un « % de titres en croissance » sur trois titres. La même faute, ailleurs, passerait
sous ce test sans le faire rougir.
"""
from datetime import datetime, timezone

import pandas as pd

from src.dashboard.views.alerts import _essais_avant_de_douter, _trial_cohorts

_NOW = pd.Timestamp("2026-09-22 12:00:00")


def _aware(d: str):
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


# La production du 2026-09-22, telle quelle.
_ETATS = pd.DataFrame([
    (1,  _aware("2026-03-10"), None,      None,                 None, "premium"),
    (10, _aware("2026-06-14"), None,      None,                 None, "free"),
    (11, _aware("2026-06-14"), "premium", _aware("2026-07-14"), None, "free"),
    (12, _aware("2026-06-15"), "premium", _aware("2026-07-15"), None, "free"),
    (13, _aware("2026-08-12"), "premium", _aware("2026-09-11"), None, "free"),
    (14, _aware("2026-08-21"), None,      None,                 None, "free"),
    (17, _aware("2026-08-30"), "premium", _aware("2026-09-29"), None, "free"),
    (18, _aware("2026-08-31"), "premium", _aware("2026-10-17"), None, "free"),
], columns=["id", "created_at", "promo_plan", "promo_plan_expires_at",
            "subscription_plan", "tier"])

_VIDE = pd.DataFrame(columns=["artist_id", "plan", "changed_at", "source"])


def test_the_cohort_matches_what_production_holds():
    coh = _trial_cohorts(_ETATS, _VIDE, _NOW)
    assert int(coh["accordes"].sum()) == 5
    assert int(coh["termines"].sum()) == 3
    assert int(coh["payants"].sum()) == 0


def test_an_account_without_a_trial_is_not_in_the_cohort():
    """Le propriétaire (artiste 1) est Premium et n'a jamais eu d'essai.

    Le compter parmi les essais convertis afficherait un taux flatteur et faux.
    """
    coh = _trial_cohorts(_ETATS, _VIDE, _NOW)
    assert int(coh["accordes"].sum()) == 5, "8 artistes, 5 essais — pas 8"


def test_a_running_trial_is_not_counted_as_a_failure():
    """L'artiste 18 court jusqu'au 2026-10-17 : il n'est pas au dénominateur.

    C'est le défaut classique de la mesure de cohorte — mettre les essais EN COURS
    au dénominateur les compte comme des échecs et écrase le taux vers zéro.
    """
    coh = _trial_cohorts(_ETATS, _VIDE, _NOW)
    aout = coh[coh["Cohorte"] == "2026-08"].iloc[0]
    assert int(aout["accordes"]) == 3
    assert int(aout["termines"]) == 1, (
        "seul l'artiste 13 (clos le 2026-09-11) est arrivé à terme en août ; "
        "17 clôt le 2026-09-29 et 18 le 2026-10-17"
    )


def test_a_paying_subscription_counts_as_a_conversion():
    """Le sens inverse : une vraie conversion doit être VUE.

    Sans ce cas, une fonction qui rendrait toujours zéro passerait les trois tests
    précédents. C'est la mutation qui compte.
    """
    etats = _ETATS.copy()
    etats.loc[etats["id"] == 11, "subscription_plan"] = "premium"
    coh = _trial_cohorts(etats, _VIDE, _NOW)
    assert int(coh["payants"].sum()) == 1


def test_a_stripe_row_after_the_trial_end_counts_too():
    """L'autre chemin : la ligne de journal du webhook, sans table d'abonnement.

    En production l'artiste 1 porte exactement ce cas — `stripe_webhook` dans le
    journal, aucune ligne d'abonnement. Une cohorte qui ne lirait que
    `artist_subscriptions` raterait ce genre de conversion.
    """
    hist = pd.DataFrame([
        (13, "premium", pd.Timestamp("2026-09-15"), "stripe_webhook"),
    ], columns=["artist_id", "plan", "changed_at", "source"])
    coh = _trial_cohorts(_ETATS, hist, _NOW)
    assert int(coh["payants"].sum()) == 1


def test_a_stripe_row_BEFORE_the_trial_end_is_not_a_trial_conversion():
    """Faux positif à écarter : payer PENDANT l'essai n'est pas y avoir survécu.

    Un paiement antérieur à la fin de l'essai est un achat anticipé — le compter
    comme « l'essai a converti » mélange deux évènements distincts.
    """
    hist = pd.DataFrame([
        (13, "premium", pd.Timestamp("2026-08-20"), "stripe_webhook"),
    ], columns=["artist_id", "plan", "changed_at", "source"])
    coh = _trial_cohorts(_ETATS, hist, _NOW)
    assert int(coh["payants"].sum()) == 0


def test_the_threshold_is_computed_not_guessed():
    """19 essais : le premier n tel que 0,85**n < 5 %.

    Le nombre doit SUIVRE le repère. S'il ne bouge pas quand le repère change,
    c'est une constante déguisée en calcul.
    """
    assert _essais_avant_de_douter() == 19
    assert 0.85 ** 19 < 0.05 <= 0.85 ** 18
    # il suit son repère — un essai qui convertit mieux demande moins d'observations
    assert _essais_avant_de_douter(repere=0.50) == 5
    assert _essais_avant_de_douter(repere=0.05) == 59


def test_three_trials_are_below_the_threshold():
    """Le fait qui a fait écrire toute cette section, énoncé une fois."""
    coh = _trial_cohorts(_ETATS, _VIDE, _NOW)
    assert int(coh["termines"].sum()) < _essais_avant_de_douter(), (
        "si ce test devient faux, la production a assez d'essais pour qu'un taux "
        "veuille dire quelque chose — c'est une bonne nouvelle, pas une régression"
    )
