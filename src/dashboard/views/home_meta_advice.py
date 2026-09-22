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
faire entrer Shazam sans un aller-retour de plus. L'accueil est à **14 sur 14** pour
un artiste (13 sur 13 en admin), mesuré le 2026-09-22 par le script du garde lui-même,
et ce plafond ne monte pas.

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

from datetime import date

import streamlit as st

from src.dashboard.utils.date_format import format_date
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


def _euros(v: float) -> str:
    """Un montant, espace fine insécable en millier, sans décimale."""
    return f"{v:,.0f}".replace(",", " ")


def _ligne_argent(side: dict) -> None:
    """Ce qui est SORTI et ce qui est RENTRÉ — deux nombres, aucun verdict.

    ⚠️ AUCUN HORIZON ICI, ET C'EST MESURÉ, pas prudentiel.

    Le point mort existe déjà — `utils/artist_cashflow.break_even()` — et il est
    mieux fait que ce qu'on écrirait à la hâte : quatre états, dont un `jamais` qui
    refuse d'inventer une date parce que « en inventer une lointaine serait un
    mensonge poli ». Il vit sur 📈 Prévisions revenus, et l'accueil y RENVOIE.

    Le recopier ici demanderait la série mensuelle, donc une requête — et l'accueil
    est à 14 sur 14. Le recalculer en SQL DIVERGE, vérifié le 2026-09-22 :

        forward_rate via monthly_net (mois vides remis à zéro)  2,20 €/mois
        la même question en SQL, mois existants seulement       0,98 €/mois

    ×2,2 sur le rythme, donc sur l'horizon — 107 ans contre 241. `monthly_net`
    réintroduit les mois sans mouvement à zéro parce qu'« un mois sans mouvement est
    un mois à zéro, pas un mois qui n'existe pas ». Recopier cette règle, c'est la
    faire diverger.

    Les deux sommes ci-dessous, elles, n'ont besoin d'aucune interpolation.
    """
    sorti, rentre = side.get("cash_sorti"), side.get("cash_rentre")
    if not sorti:
        return

    if rentre is None:
        # PAS DE « 0 € ». Un artiste qui n'a jamais déposé de relevé lirait une
        # faillite là où il n'y a qu'un fichier manquant. La carte d'absence du
        # distributeur, plus haut sur la page, porte déjà le geste.
        st.caption(t(
            "home.money_no_revenue",
            "Tu n'as pas encore déposé de relevé de distributeur : impossible de "
            "dire ce que cette dépense t'a rapporté."))
        return

    st.markdown(t(
        "home.money_line",
        "Investi **{sorti} €** · Rentré **{rentre} €**").format(
            sorti=_euros(sorti), rentre=_euros(rentre)))
    # LA RÉSERVE EST OBLIGATOIRE : ce sont les revenus QU'IL A DÉPOSÉS, sur toute
    # sa carrière, face à une dépense qui peut s'être arrêtée il y a deux ans. Sans
    # elle, deux nombres côte à côte se lisent comme un bilan.
    st.caption(t(
        "home.money_caveat",
        "Depuis le début, hors période affichée. Les revenus sont ceux que tu as "
        "importés — distributeurs et SACEM. Le point mort, lui, se calcule sur "
        "📈 Prévisions revenus."))


#: Le nom lisible de chaque axe. Déclaré ici et non dans `meta_axes` : ce module-là
#: est pur et ne connaît pas `t()`.
_AXE_NOM = {
    "age": lambda: t("home.axe_age", "la tranche d'âge"),
    "pays": lambda: t("home.axe_pays", "le pays"),
    "placement": lambda: t("home.axe_placement", "l'emplacement de l'annonce"),
}


def _axes_de(side: dict):
    """Les trois axes, classés — ou une liste vide.

    Les lignes brutes arrivent en JSON dans `side["axes"]` ; le classement, le
    plancher de fiabilité et le refus de conclure vivent dans `utils/meta_axes.py`.
    """
    from src.dashboard.utils.meta_axes import Ligne, classer_axes

    brutes = side.get("axes") or {}
    axes = {}
    for nom, lignes in brutes.items():
        axes[nom] = [Ligne(str(x.get("v")), float(x.get("d") or 0),
                           float(x.get("r") or 0))
                     for x in (lignes or []) if x.get("v")]
    return classer_axes(axes)


def _lisible(valeur: str) -> str:
    """Un nom d'emplacement sans la répétition de sa plateforme.

    Meta nomme ses emplacements en répétant le réseau : `instagram_reels`,
    `facebook_reels`, `instagram_stories`. Collé à sa plateforme par la requête, ça
    donne « instagram / instagram_reels » — lisible par une machine, pas par un
    artiste. Défaut vu en regardant le rendu, pas en lisant le code.
    """
    if " / " not in valeur:
        return valeur
    plateforme, emplacement = valeur.split(" / ", 1)
    if emplacement.startswith(plateforme + "_"):
        emplacement = emplacement[len(plateforme) + 1:]
    return f"{plateforme} / {emplacement.replace('_', ' ')}"


def _phrase_ecart(e) -> str:
    """Une phrase, et le mot « environ » n'est pas une politesse.

    `gaspillage` suppose que le volume aurait suivi au meilleur coût, ce que rien ne
    garantit. C'est un ordre de grandeur, et il doit se lire comme tel.
    """
    return t(
        "home.axe_phrase",
        "Sur **{axe}**, ton meilleur résultat est **{meilleur}** à {cpr_min} € le "
        "clic sortant, et ton pire **{pire}** à {cpr_max} €. Environ **{perte} €** "
        "sont partis au-dessus du meilleur coût.").format(
            axe=_AXE_NOM.get(e.dimension, lambda: e.dimension)(),
            meilleur=_lisible(e.meilleur), pire=_lisible(e.pire),
            cpr_min=f"{e.cpr_min:.3f}".replace(".", ","),
            cpr_max=f"{e.cpr_max:.3f}".replace(".", ","),
            perte=f"{e.gaspillage:,.0f}".replace(",", " "))


def _bloc_axes(side: dict) -> None:
    """Le pire écart en clair, les deux autres repliés.

    ⚠️ LE PIRE EN EUROS, PAS EN RAPPORT — et l'écart entre les deux classements est
    mesuré, pas théorique. Sur le catalogue de l'artiste 1 le 2026-09-22 :

        par rapport      pays ×1,92  >  âge ×1,67  >  placement ×1,27
        par euros        âge ~768 €  >  pays ~289 €  >  placement ~182 €

    Le pays a le rapport le plus spectaculaire et coûte **2,7 fois moins cher** que
    l'âge. Classer par rapport aurait envoyé l'artiste chasser le mauvais écart.

    ⚠️ Et un classement de coût par clic NE SAIT PAS ce qu'un clic vaut. La ligne la
    moins chère du catalogue est `audience_network/rewarded_video` — des clics posés
    pour obtenir une récompense de jeu. Le plancher de dépense l'écarte ici par
    chance, pas par construction : la réserve du proxy est donc obligatoire.
    """
    ecarts = _axes_de(side)
    if not ecarts:
        return
    st.markdown(_phrase_ecart(ecarts[0]))
    reste = ecarts[1:]
    if not reste:
        return
    titre = t("home.axes_reste", "Les {n} autres axes, moins coûteux").format(
        n=len(reste))
    with st.expander(titre, expanded=False):
        for e in reste:
            st.markdown(_phrase_ecart(e))


def _ligne_activite(side: dict) -> None:
    """Ce que la lecture a RAMENÉ, et depuis quand plus rien ne tourne.

    ⚠️ TROIS ÉTATS, ET ILS NE SE CONFONDENT PAS. C'est la règle « une lecture qui
    échoue ne se déguise pas en rien à lire » de `.claude/rules/python.md`, appliquée
    à un écran plutôt qu'à un `except` :

      * **une campagne tourne** → on ne dit rien. Le silence est le bon message ;
        annoncer « tout va bien » à chaque rendu apprend à sauter la ligne.
      * **aucune ne tourne, et on le SAIT** — `meta_campaigns` porte des lignes et
        aucune n'est `ACTIVE`. On le dit, avec la date de la dernière dépense.
      * **on ne sait pas** — `meta_campaigns` est vide pour ce locataire alors que la
        dépense existe. On donne la date et on s'arrête là : écrire « aucune campagne
        active » serait une affirmation qu'aucune donnée ne soutient.

    Pourquoi le STATUT et pas la date
    ----------------------------------
    « La dernière dépense est vieille » et « aucune campagne ne tourne » sont deux
    faits distincts. Une campagne `ACTIVE` à budget épuisé ne dépense plus et tourne
    toujours. La source de vérité est donc `meta_campaigns.status`, celle que
    `freshness_monitor` prend déjà pour taire son alerte (`meta_no_active_campaign`) —
    on ne s'en invente pas une seconde.

    Mesuré en production le 2026-09-22, artiste 1 : **19 ARCHIVED, 15 PAUSED, zéro
    ACTIVE**, et `MAX(day)` au **2024-09-30** — 722 jours — pendant que
    `MAX(collected_at)` vaut le JOUR MÊME, parce que le DAG réécrit chaque matin les
    mêmes lignes de 2024.

    Pourquoi cette ligne confirme que la lecture a MARCHÉ
    -----------------------------------------------------
    `period_side_metrics` rend `{}` sur exception, et `render_meta_advice` ne dessine
    rien sans dépense. **Atteindre cette ligne prouve donc que la requête est passée
    et a ramené des chiffres** : le seul état ambigu qui restait est « ces chiffres
    sont-ils d'aujourd'hui ? », et c'est exactement ce qu'elle tranche. Elle ne
    proclame pas un succès technique — elle date ce qui est à l'écran.
    """
    jour = side.get("meta_last_day")
    actives = side.get("meta_active")
    connues = side.get("meta_campaigns_known") or 0

    if actives:
        return                       # ça tourne : le silence est le bon message

    if jour is None:
        return                       # aucune dépense datée : rien à situer

    depuis = (date.today() - jour).days
    jour_txt = format_date(jour)

    if connues:
        st.info(t(
            "home.advice_no_active",
            "✅ Tes données Meta sont bien remontées — et **aucune campagne n'est "
            "active aujourd'hui**. La dernière dépense date du **{jour}**, il y a "
            "**{depuis} jours**. Les chiffres ci-dessus décrivent donc cette "
            "campagne-là, pas ce qui tourne en ce moment.").format(
                jour=jour_txt, depuis=f"{depuis:,}".replace(",", " ")))
    else:
        # `meta_campaigns` vide : la dépense est là, le statut ne l'est pas.
        st.info(t(
            "home.advice_last_spend_only",
            "✅ Tes données Meta sont bien remontées : la dernière dépense date du "
            "**{jour}**, il y a **{depuis} jours**. Nous n'avons pas encore la liste "
            "de tes campagnes, donc nous ne pouvons pas dire si l'une tourne "
            "encore.").format(jour=jour_txt,
                              depuis=f"{depuis:,}".replace(",", " ")))


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

    # ⚠️ LA PHRASE DE PÉRIODE NE S'AFFICHE QUE SI ELLE DIT AUTRE CHOSE que la
    # ligne « Investi / Rentré » juste en dessous. Défaut trouvé en REGARDANT le
    # rendu : sur le filtre « Depuis le début », les deux portaient le MÊME nombre,
    # à une ligne d'intervalle — « tu as dépensé 3 088 € » puis « Investi 3 088 € ».
    #
    # Elles ne sont pas redondantes par nature : celle-ci est bornée à la période
    # affichée, l'autre porte toute la carrière. Elles coïncident quand la période
    # couvre tout, et c'est le cas par défaut — donc le cas que la plupart voient.
    _sorti = side.get("cash_sorti")
    if _sorti is None or round(_sorti) != round(depense):
        st.markdown(t(
            "home.advice_spend",
            "Sur la période, tu as dépensé **{depense} €** en publicité.").format(
                depense=f"{depense:,.0f}".replace(",", " ")))

    _ligne_argent(side)

    if not (cpr and nom):
        st.caption(t("home.advice_no_campaign",
                     "Aucune campagne ne porte encore de coût par résultat "
                     "exploitable."))
        return

    # ⚠️ LA DATE VOYAGE AVEC LE CHIFFRE. Sans elle, « 0,109 € le clic » se lit au
    # présent — et en production le dernier jour de dépense est le **30/09/2024**,
    # soit 722 jours. Le coût est juste ; le temps de la phrase était faux.
    _jour = side.get("best_cpr_last_day")
    if _jour:
        st.markdown(t(
            "home.advice_best_dated",
            "Ta campagne la moins chère est **{nom}** : **{cpr} €** le clic sortant, "
            "sur ses dépenses jusqu'au **{jour}**.")
            .format(nom=nom, cpr=f"{cpr:.3f}".replace(".", ","),
                    jour=format_date(_jour)))
    else:
        st.markdown(t(
            "home.advice_best",
            "Ta campagne la moins chère est **{nom}** : **{cpr} €** le clic sortant.")
            .format(nom=nom, cpr=f"{cpr:.3f}".replace(".", ",")))
    # ⚠️ LA RÉSERVE VOYAGE AVEC LE CHIFFRE. Un clic sortant n'est pas une écoute :
    # la phrase canonique vit dans `proxy_disclosure` et n'est pas réécrite ici.
    st.caption(cpr_help())

    _bloc_axes(side)

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

    _ligne_activite(side)

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
