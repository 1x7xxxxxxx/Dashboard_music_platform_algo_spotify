"""🎛️ Comment régler tes campagnes — tous les paramètres, au même endroit.

Type: Sub
Uses: streamlit, pandas, ._reglages, src.dashboard.utils.artist_cashflow
Depends on: meta_campaigns, meta_ads, meta_insights, v_meta_daily, v_s4a_song_daily
Triggers: views/trigger_algo/_tab_budget_roi.py
Persists in: nothing

Ce que ce panneau rassemble, et pourquoi il n'existait pas
-----------------------------------------------------------
Les réglages d'une campagne vivaient éparpillés : l'appel à l'action dans un tableau
de l'onglet Explainabilité, l'objectif nulle part, la créative dans une vue séparée,
le budget dans un troisième onglet et le point mort dans une autre page. Un artiste
qui veut savoir « qu'est-ce que je change ? » devait les visiter tous et faire la
comparaison de tête.

Les quatre axes sont mesurés sur la MÊME base, à la MÊME maille, et classés par leur
effet réel. Production, 2026-09-22 :

    appel à l'action   LISTEN_NOW 0,1177 €/clic  contre  0,2117 € sans   → ×1,8
    objectif           OUTCOME_ENGAGEMENT 0,1256 contre CONVERSIONS 0,2279
    créative (titre)   « Listen now ! » 0,0771   contre  0,2279          → ×3,0
    sans titre         0,2192 €/clic — 2,8 fois la meilleure créative

⚠️ **LE PIÈGE QUE CE PANNEAU EXISTE POUR ÉVITER**
Les effectifs vont de **1 annonce à 84**, les dépenses de **13 € à 5 198 €**.
`MESSAGE_PAGE` à 1,45 €/clic est UNE annonce ; `VIDEO_VIEWS` à 2,72 €/clic sont
deux campagnes et trente euros. Présenter ces lignes comme un enseignement
produirait un conseil — « ne fais jamais de vidéo » — que la donnée ne porte pas.
Chaque ligne porte donc son effectif et sa dépense, les lignes trop minces sont
marquées et **ne peuvent jamais prendre la tête d'un classement**, et une
recommandation exige **deux** lignes fiables : un « meilleur » sans rival mesuré
n'est pas un enseignement, c'est la seule chose qu'on ait essayée.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import secondary_analyses

from ._reglages import budget_pour_streams, classer, recommandation

_Q_AXE = {
    "cta": """
        SELECT a.call_to_action AS valeur, COUNT(DISTINCT a.ad_id) AS ads,
               SUM(i.spend) AS depense, SUM(i.clicks) AS clics,
               SUM(i.impressions) AS impressions
          FROM meta_ads a JOIN meta_insights i ON i.ad_id = a.ad_id
         WHERE a.artist_id = %s GROUP BY 1
    """,
    "objectif": """
        SELECT c.objective AS valeur, COUNT(DISTINCT a.ad_id) AS ads,
               SUM(i.spend) AS depense, SUM(i.clicks) AS clics,
               SUM(i.impressions) AS impressions
          FROM meta_campaigns c
          JOIN meta_ads a ON a.campaign_id = c.campaign_id
          JOIN meta_insights i ON i.ad_id = a.ad_id
         WHERE c.artist_id = %s GROUP BY 1
    """,
    "creative": """
        SELECT a.title AS valeur, COUNT(DISTINCT a.ad_id) AS ads,
               SUM(i.spend) AS depense, SUM(i.clicks) AS clics,
               SUM(i.impressions) AS impressions
          FROM meta_ads a JOIN meta_insights i ON i.ad_id = a.ad_id
         WHERE a.artist_id = %s GROUP BY 1
    """,
}

_LIBELLES = {
    "cta": ("👆 Le bouton d'appel à l'action", "Appel à l'action"),
    "objectif": ("🎯 L'objectif de la campagne", "Objectif"),
    "creative": ("🎨 Le titre de la créative", "Créative"),
}


def _lire_axe(db, artist_id: int, axe: str) -> pd.DataFrame:
    try:
        rows = db.fetch_query(_Q_AXE[axe], (artist_id,))
    except Exception:                                    # noqa: BLE001
        return pd.DataFrame()
    colonnes = ["valeur", "ads", "depense", "clics", "impressions"]
    return classer([dict(zip(colonnes, r)) for r in (rows or [])],
                   _LIBELLES[axe][1])


def _rendre_axe(titre: str, df: pd.DataFrame) -> dict | None:
    st.markdown(f"**{titre}**")
    if df.empty:
        st.caption(t("trigger_algo.reg.axis_empty", "Pas encore de données sur cet axe."))
        return None
    aff = pd.DataFrame({
        t("trigger_algo.reg.col_value", "Réglage"): [
            v if f else f"{v} ⚠️" for v, f in zip(df["valeur"], df["fiable"])],
        t("trigger_algo.reg.col_ads", "Annonces"): df["ads"],
        t("trigger_algo.reg.col_spend", "Dépensé"): [
            f"{v:,.0f} €".replace(",", " ") for v in df["depense"]],
        t("trigger_algo.reg.col_cpc", "Coût / clic"): [
            "—" if pd.isna(v) else f"{v:,.4f} €".replace(",", " ") for v in df["cpc"]],
        t("trigger_algo.reg.col_ctr", "Taux de clic"): [
            "—" if pd.isna(v) else f"{v:.2f} %" for v in df["ctr"]],
    })
    st.dataframe(aff, hide_index=True, width="stretch")
    reco = recommandation(df)
    if reco:
        # ⚠️ L'espacement des milliers s'applique au NOMBRE, pas à la phrase.
        # Le premier jet faisait `.format(...).replace(",", " ")` sur la chaîne
        # entière : il remplaçait aussi la virgule de « …€ », soit… » et rendait
        # « 0.2117 € pour « X »  soit 1.8 fois ».
        st.success(t(
            "trigger_algo.reg.reco",
            "✅ **Garde « {retenir} »** — {cpc_min:.4f} € le clic contre "
            "{cpc_max:.4f} € pour « {eviter} », soit **{facteur:.1f} fois moins cher**. "
            "Mesuré sur {ads} annonces et {dep} €."
        ).format(retenir=reco["retenir"], cpc_min=reco["cpc_min"],
                 cpc_max=reco["cpc_max"], eviter=reco["eviter"],
                 facteur=reco["facteur"], ads=reco["sur_ads"],
                 dep=f"{reco['sur_depense']:,.0f}".replace(",", " ")))
    else:
        st.caption(t(
            "trigger_algo.reg.no_reco",
            "Pas de recommandation sur cet axe : il faut **deux** réglages comparés "
            "sur assez d'annonces. Un seul essai n'est pas un enseignement."))
    return reco


def _show_reglages(db, artist_id, ml_pred: dict | None,
                   cout_par_stream: float | None) -> None:
    """Le panneau complet : les réglages, le budget de déclenchement, le retour."""
    st.subheader(t("trigger_algo.reg.header",
                   "🎛️ Comment régler tes campagnes"))
    if not artist_id:
        st.info(t("trigger_algo.reg.admin", "Sélectionne un artiste."))
        return

    st.caption(t(
        "trigger_algo.reg.intro",
        "Tout ce qui se règle sur une campagne, classé par ce que ça change "
        "RÉELLEMENT sur ton compte — pas par ce qu'on lit ailleurs. Un réglage "
        "marqué ⚠️ repose sur trop peu d'annonces pour en tirer une leçon."))

    recos = []
    for axe, (titre, _nom) in _LIBELLES.items():
        reco = _rendre_axe(titre, _lire_axe(db, artist_id, axe))
        if reco:
            recos.append(reco)
        st.markdown("")

    if recos:
        gains = " · ".join(
            f"**{r['retenir']}** (×{r['facteur']:.1f})" for r in recos)
        st.info(t("trigger_algo.reg.summary",
                  "📌 **À retenir, tous axes confondus** : {gains}").format(gains=gains))

    _budget_declenchement(ml_pred, cout_par_stream)
    _retour_sur_investissement(db, artist_id)


def _budget_declenchement(ml_pred: dict | None, cout_par_stream: float | None) -> None:
    """Ce que coûterait d'acheter les écoutes qui manquent à chaque porte."""
    st.markdown("**" + t("trigger_algo.reg.budget_header",
                         "💰 Le budget pour déclencher chaque playlist") + "**")
    if not ml_pred:
        st.caption(t("trigger_algo.reg.budget_nopred",
                     "Pas encore de prédiction pour ce titre."))
        return
    feats = ml_pred.get("features_json") or {}
    if isinstance(feats, str):
        import json
        try:
            feats = json.loads(feats)
        except (ValueError, TypeError):
            feats = {}

    from src.dashboard.utils.algo_knowledge import split_coach_actions

    lignes = []
    for algo, nom in (("DW", "Discover Weekly"), ("RR", "Release Radar"),
                      ("RADIO", "Radio")):
        titre_lv, _artiste = split_coach_actions(algo, feats)
        streams = next((a for a in titre_lv
                        if a["feature"] == "StreamsLast7Days"), None)
        if not streams:
            continue
        cout = budget_pour_streams(streams["gap"], cout_par_stream)
        lignes.append({
            t("trigger_algo.reg.col_algo", "Playlist"): nom,
            t("trigger_algo.reg.col_missing", "Écoutes qui manquent (7 j)"):
                f"{streams['gap']:,.0f}".replace(",", " "),
            t("trigger_algo.reg.col_budget", "Ordre de grandeur"):
                "—" if cout is None else f"{cout:,.0f} €".replace(",", " "),
        })
    if not lignes:
        st.caption(t("trigger_algo.reg.budget_none",
                     "Aucune porte n'attend d'écoutes supplémentaires sur ce titre."))
        return

    # ⚠️ LES TROIS PORTES PARTAGENT LA MÊME CIBLE D'ÉCOUTES (2 000 sur 7 jours),
    # donc les trois lignes sont identiques au mot près. Les empiler laisserait
    # croire à trois budgets à cumuler, alors que c'est UN budget qui débloque la
    # condition d'écoutes des trois. On replie, et on écrit pourquoi.
    distinctes = {tuple(sorted(x.items())) for x in
                  [{k: v for k, v in ligne.items()
                    if "Playlist" not in k} for ligne in lignes]}
    if len(distinctes) == 1 and len(lignes) > 1:
        seule = lignes[0]
        manque = seule[t("trigger_algo.reg.col_missing", "Écoutes qui manquent (7 j)")]
        budget = seule[t("trigger_algo.reg.col_budget", "Ordre de grandeur")]
        st.info(t(
            "trigger_algo.reg.budget_shared",
            "Les **{n} playlists demandent la MÊME chose** sur ce point : "
            "**{manque} écoutes** sur 7 jours, soit **{budget}**. Ce n'est pas trois "
            "budgets à cumuler — c'est un seul, qui débloque la condition d'écoutes "
            "des trois."
        ).format(n=len(lignes), manque=manque, budget=budget))
    else:
        st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    st.caption(t(
        "trigger_algo.reg.budget_caveat",
        "⚠️ **Un ordre de grandeur, pas un devis.** Le coût par écoute est agrégé sur "
        "TOUTES tes campagnes et TOUS tes titres : il ne dit pas ce que coûtent les "
        "écoutes de celui-ci. L'attribution par titre demanderait une correspondance "
        "campagne↔titre, qui n'existe que pour 19 titres, et une dépense publicitaire "
        "qui ne s'arrête pas en septembre 2024."))


def _retour_sur_investissement(db, artist_id) -> None:
    """Dans combien de temps la publicité est remboursée — ou jamais."""
    with secondary_analyses(t("trigger_algo.reg.roi_header",
                              "⏳ Dans combien de temps c'est remboursé")):
        # La MÊME porte que « 📈 Prévisions revenus » — `v_artist_monthly_cashflow`
        # puis `monthly_net`. Reconstruire la série autrement donnerait deux points
        # morts pour le même artiste, et c'est le genre de divergence que ce dépôt
        # a déjà payée sur le MRR (trois définitions, deux réponses).
        try:
            from src.dashboard.utils.artist_cashflow import break_even, monthly_net

            cashflow = db.fetch_df(
                "SELECT year, month, flux, source, amount_eur, direction "
                "FROM v_artist_monthly_cashflow WHERE artist_id = %s", (artist_id,))
            etat = break_even(monthly_net(cashflow))
        except Exception:                                # noqa: BLE001
            st.caption(t("trigger_algo.reg.roi_unreadable",
                         "Série mensuelle illisible — ce n'est pas « pas de données »."))
            return

        quoi = etat.get("etat")
        if quoi == "deja":
            st.success(t("trigger_algo.reg.roi_done",
                         "✅ Tu es déjà rentré dans tes frais : cumul net "
                         "**{cumul:,.2f} €**.").format(cumul=etat["cumul"]).replace(",", " "))
        elif quoi == "atteint":
            st.info(t("trigger_algo.reg.roi_date",
                      "Au rythme des derniers mois (**{rythme:,.2f} €/mois**), le point "
                      "mort tombe dans **{mois} mois** — {date}.")
                    .format(rythme=etat["rythme"], mois=etat["mois"],
                            date=etat["date"]).replace(",", " "))
        elif quoi == "jamais":
            st.warning(t(
                "trigger_algo.reg.roi_never",
                "⛔ **Au rythme actuel, jamais.** Le net mensuel est nul ou négatif "
                "(**{rythme:,.2f} €/mois** pour un cumul de **{cumul:,.2f} €**). "
                "Inventer une date lointaine serait un mensonge poli : ce qu'il faut "
                "changer n'est pas la patience."
            ).format(rythme=etat["rythme"], cumul=etat["cumul"]).replace(",", " "))
        else:
            st.caption(t("trigger_algo.reg.roi_unknown",
                         "Pas encore assez d'historique pour dire quand."))
