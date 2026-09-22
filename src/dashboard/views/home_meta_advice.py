"""Ce que les chiffres Meta de l'accueil permettent de DÉCIDER — en phrases.

Type: Sub
Uses: streamlit, meta_confidence, proxy_disclosure, plan_gate
Depends on: les clés Meta de `period_side_metrics` — déjà en mémoire
Triggers: views/home.py
Persists in: nothing

Pourquoi des phrases, et pas des jauges
----------------------------------------
`home_tiles.py` porte **6 `st.metric` pour un plafond de 6**
(`.claude/dev-docs/first-screen-ceilings.json`) : une jauge de plus fait rougir le
cliquet du premier écran. Ce n'est pas une contrainte subie — c'est la bonne forme.

Croll & Yoskovitz, *Lean Analytics* : une métrique de vanité fait plaisir, une
métrique actionnable **change une décision**. « 3 087 € dépensés » est un chiffre ;
« ta meilleure campagne paie 0,11 € le clic sortant, et c'est mesuré sur assez de
monde pour s'y fier » est une décision. La seconde a besoin d'une phrase.

⚠️ ZÉRO REQUÊTE, et c'est STRUCTUREL
--------------------------------------
Ce module ne reçoit ni `db` ni `artist_id` : il ne peut pas interroger la base même
si quelqu'un le lui demandait. Tout vient de `_side`, le dictionnaire que l'unique
requête de `period_side_metrics` a déjà rendu — le même motif que R106 a utilisé pour
faire entrer Shazam sans un aller-retour de plus. L'accueil est à 13 requêtes pour un
plafond de 13, et ce plafond ne monte pas.

Ce que ce module REFUSE de dire
---------------------------------
**La tranche d'âge la moins chère.** Elle est mesurée, contre-intuitive et
actionnable — 35-44 convertissent 57 % moins cher que 18-24, et 78 % du budget part
sur les deux tranches les plus chères — mais elle vit dans
`meta_insights_performance_age`, une requête que l'accueil n'a pas les moyens de
payer. Elle reste sur le CPR Optimizer, vers lequel ce bloc renvoie.

**Un verdict de réglage.** `trigger_algo/_reglages.recommandation()` exige DEUX
lignes fiables — « un meilleur sans rival mesuré n'est pas un enseignement, c'est la
seule chose qu'on ait essayée ». L'accueil n'a qu'une campagne. Recopier le verdict
ici serait exactement le défaut que ce module-là existe pour refuser : conseiller
« ne fais jamais de vidéo » sur la foi de deux campagnes à 30 €.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.meta_confidence import confidence_factor
from src.dashboard.utils.plan_gate import bouton_vers, note_de_plan
from src.dashboard.utils.proxy_disclosure import cpr_help

#: En dessous, on ne tire aucune conclusion — on dit qu'on ne peut pas.
#:
#: 0,5 est le point où `confidence_factor(n) = n/(n+300)` vaut la moitié, soit
#: 300 résultats. Ce n'est pas un seuil de modèle : c'est la borne en dessous de
#: laquelle le classement de CE catalogue s'inverse d'une annonce à l'autre.
CONFIANCE_MIN = 0.5

#: La dépense en dessous de laquelle une campagne n'enseigne rien. Reprise de
#: `trigger_algo/_reglages.MIN_DEPENSE` — la même borne, pas une seconde copie.
DEPENSE_MIN = 100.0


def _resultats(depense: float | None, cpr: float | None) -> float | None:
    """Combien de résultats cette dépense a payés — DÉRIVÉ, jamais interrogé.

    `cpr` est un coût PAR résultat, donc `dépense / cpr` rend leur nombre. La
    division passe par des `numeric` et peut rendre 1 172,9997 là où la vérité est
    1 173 : ce nombre ne doit donc JAMAIS être affiché comme un effectif. Il ne sert
    qu'à peser la confiance, qui est lisse — un verdict ne bascule pas sur 0,03.
    """
    if not depense or not cpr:
        return None
    return depense / cpr


def render_meta_advice(side: dict) -> None:
    """Trois phrases sur ce que la publicité a appris, ou le refus de conclure.

    Rend `None` sans rien dessiner quand il n'y a pas de dépense : un bloc de
    conseil sur zéro euro dépensé est du bruit sur l'écran de quelqu'un qui n'a
    jamais fait de publicité.
    """
    depense = side.get("meta_spend") or 0
    if not depense:
        return

    st.subheader(t("home.advice_header", "📱 Ce que ta publicité a appris"))
    note_de_plan("meta_cpr_optimizer")

    cpr = side.get("best_cpr")
    nom = side.get("best_cpr_name")
    depense_campagne = side.get("best_cpr_spend")

    st.markdown(t(
        "home.advice_spend",
        "Sur la période, tu as dépensé **{depense} €** en publicité.").format(
            depense=f"{depense:,.0f}".replace(",", " ")))

    if not (cpr and nom):
        st.caption(t("home.advice_no_campaign",
                     "Aucune campagne ne porte encore de coût par résultat "
                     "exploitable."))
        return

    st.markdown(t(
        "home.advice_best",
        "Ta campagne la moins chère est **{nom}** : **{cpr} €** le clic sortant.")
        .format(nom=nom, cpr=f"{cpr:.3f}".replace(".", ",")))
    # ⚠️ LA RÉSERVE VOYAGE AVEC LE CHIFFRE. Un clic sortant n'est pas une écoute :
    # la phrase canonique vit dans `proxy_disclosure` et n'est pas réécrite ici.
    st.caption(cpr_help())

    n = _resultats(depense_campagne, cpr)
    confiance = confidence_factor(n) if n else 0.0

    if confiance < CONFIANCE_MIN or (depense_campagne or 0) < DEPENSE_MIN:
        # LE REFUS EST UNE RÉPONSE, et il se dit. Une moyenne calculée sur trois
        # clics a l'air d'un enseignement et n'en est pas ; la taire laisserait
        # croire qu'il n'y a rien à savoir, l'annoncer serait pire.
        st.caption(t(
            "home.advice_too_thin",
            "⚠️ C'est mesuré sur trop peu pour en tirer une règle — laisse tourner, "
            "ou compare tes campagnes en détail."))
    else:
        st.caption(t(
            "home.advice_solid",
            "C'est mesuré sur **{depense} €** de cette campagne : assez pour s'y "
            "fier.").format(
                depense=f"{depense_campagne:,.0f}".replace(",", " ")))

    # Le renvoi vers ce que l'accueil ne peut PAS payer : la comparaison complète,
    # la tranche d'âge la moins chère, et les budgets à monter ou à baisser.
    if bouton_vers(
        "meta_cpr_optimizer",
        ouvert=t("home.advice_cta", "📊 Comparer toutes mes campagnes"),
        ferme=t("home.advice_cta_locked", "Comparer toutes mes campagnes"),
        aide_ouvert=t("home.advice_cta_help",
                      "Le score par campagne, la tranche d'âge la moins chère, et "
                      "les budgets à monter ou à baisser."),
        aide_ferme=t("home.advice_cta_locked_help",
                     "La comparaison détaillée de tes campagnes est comprise dans "
                     "l'abonnement."),
        key="home_to_cpr",
    ):
        from src.dashboard.utils.navigation import goto
        goto("meta_cpr_optimizer")
