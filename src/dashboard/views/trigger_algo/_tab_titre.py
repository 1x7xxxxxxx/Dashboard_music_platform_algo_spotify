"""🎧 Ce titre : ce qu'il reste à faire — le Pareto et son équivalent en argent.

Type: Sub
Uses: streamlit, pandas, ._pareto, src.dashboard.utils.artist_cashflow
Depends on: ml_song_predictions (reçue du routeur), algo_lifecycle_benchmark,
  imusician_sales_detail
Triggers: views/trigger_algo/router.py
Persists in: nothing

Ce que cet onglet rassemble
----------------------------
Le coach (`build_coach_actions`) existait déjà — **enterré dans l'onglet
Explainabilité**, après trois cascades SHAP en log-odds. L'argent existait aussi —
**dans une autre page** (`revenue_forecast`). Cet onglet les met côte à côte, ce qui
est très exactement ce que « regrouper les panneaux » demandait.

⚠️ LE FAIT QUE LA PAGE DOIT DIRE, ET QUE PERSONNE N'AVAIT ÉCRIT
----------------------------------------------------------------
Le Pareto est ordonné par **effort**, pas par **impact**. Mesuré sur la production
le 2026-09-22, titre « Kimono à semelle de fer - Remix » :

    levier #1  ajouts playlist   il manque   165   →  +0,06 point de chance  (+0,02 €)
    levier #3  streams 7 jours   il manque 2 000   →  +2,04 points           (+0,76 €)

Le levier le plus proche de sa cible est **trente fois moins rentable** que le plus
lointain. Un tableau qui n'afficherait que l'ordre d'effort laisserait donc l'artiste
travailler le levier le moins utile en croyant faire le plus malin. C'est pour ça que
la colonne « ce que ça rapporte » n'est pas décorative : elle est ce qui rend l'ordre
contestable, et la page invite explicitement à la lire.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils.artist_cashflow import track_stream_rate, trigger_value
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import secondary_analyses

from ._catalogue import sur_le_plancher
from ._pareto import LEVIERS_CHIFFRES, pareto

_NOMS = {"DW": "Discover Weekly", "RR": "Release Radar", "RADIO": "Radio"}


def _valeur_porte(db, artist_id, track):
    """(trame des valeurs par algo, source du taux, €/écoute) — `None` si rien."""
    taux = track_stream_rate(db, artist_id, track) if artist_id else None
    if not taux:
        return None, "aucune", None
    df = trigger_value(db, taux["eur_par_stream"])
    if df is None or df.empty:
        return None, taux["source"], taux["eur_par_stream"]
    return df, taux["source"], taux["eur_par_stream"]


def _show_tab_titre(db, track: str, artist_id, ml_pred: dict | None) -> None:
    """Le plan d'action du titre sélectionné."""
    if not ml_pred:
        from ._common import show_no_prediction_yet
        show_no_prediction_yet()
        return

    feats = ml_pred.get("features_json") or {}
    if isinstance(feats, str):
        import json
        try:
            feats = json.loads(feats)
        except (ValueError, TypeError):
            feats = {}

    valeurs, source_taux, eur_stream = _valeur_porte(db, artist_id, track)
    plan = pareto(feats, valeur_porte=_valeur_de(valeurs, None))
    if not plan:
        st.success(t("trigger_algo.titre.nothing_left",
                     "✅ Aucune métrique mesurée de ce titre n'est sous son objectif. "
                     "Rien à corriger ici — regarde l'onglet **Où en sont mes titres** "
                     "pour savoir lequel pousser."))
        return

    algo = plan["algo"]
    valeur_algo = _valeur_de(valeurs, algo)
    plan = pareto(feats, valeur_porte=valeur_algo)

    # ── L'en-tête : la porte, sa valeur, l'espérance ─────────────────────────
    proba = ml_pred.get(f"{algo.lower()}_probability")
    c1, c2, c3 = st.columns(3)
    c1.metric(t("trigger_algo.titre.tile_gate", "Porte la plus proche"), _NOMS.get(algo, algo))
    if valeur_algo:
        c2.metric(t("trigger_algo.titre.tile_value", "Ce que ça vaut si ça s'ouvre"),
                  f"{valeur_algo:,.0f} €".replace(",", " "))
        if proba is not None:
            c3.metric(t("trigger_algo.titre.tile_expect", "Espérance aujourd'hui"),
                      f"{float(proba) * valeur_algo:,.2f} €".replace(",", " "),
                      delta=(t("trigger_algo.titre.floor", "≈ plancher")
                             if sur_le_plancher(algo.lower(), proba) else None),
                      delta_color="off")

    if plan["smooth"]:
        st.warning(t("trigger_algo.titre.smooth",
                     "🐢 **{label}** est trop haut ({cur:,.2f} {unit}) — {lever}")
                   .format(label=plan["smooth"]["label"], cur=plan["smooth"]["current"],
                           unit=plan["smooth"]["unit"], lever=plan["smooth"]["lever"]))

    # ── LES TROIS PORTES CÔTE À CÔTE ────────────────────────────────────────
    # Les tuiles ci-dessus ne parlent que de la porte la PLUS PROCHE. Un artiste
    # qui décide où mettre son effort a besoin des trois : la plus proche n'est pas
    # forcément celle qui vaut le plus. Mesuré au taux d'artiste le 2026-09-22 —
    # Discover Weekly 32,81 €, Radio 22,11 €, Release Radar 9,71 € : un facteur
    # 3,4 entre la première et la dernière, que la seule porte proche masquait.
    _render_trois_portes(valeurs, ml_pred, feats)

    # ── Le Pareto ────────────────────────────────────────────────────────────
    st.subheader(t("trigger_algo.titre.pareto_header", "🪜 Ce qu'il te reste à faire"))
    _render_pareto(plan["leviers"], valeur_algo)

    if plan["artiste"]:
        txt = " · ".join(f"**{a['label']}** {a['current']:,.0f}/{a['target']:,.0f} {a['unit']}"
                         .replace(",", " ") for a in plan["artiste"][:3])
        st.info(t("trigger_algo.titre.artist_levers",
                  "🎤 **Valable pour tout ton catalogue**, pas seulement ce titre : "
                  "{levers}").format(levers=txt))

    _render_money_note(valeurs, source_taux, eur_stream)


def _render_trois_portes(valeurs, ml_pred: dict, feats: dict) -> None:
    """Les trois algos en regard : chance, valeur, espérance, et ce qui manque.

    C'est la réponse à « l'équivalent en argent pour déclencher CHAQUE algo ». Une
    seule porte affichée laisserait croire que la plus proche est la plus
    intéressante — ce que la mesure dément : Discover Weekly vaut **3,4 fois** un
    Release Radar, et c'est souvent la porte la plus lointaine.

    ⚠️ La colonne « chance » porte la marque « ≈ plancher » quand le score brut est
    négligeable. Sur les dix titres de production, **les trente probabilités** le
    sont : la colonne existe, et elle dit qu'elle ne distingue rien.
    """
    if not isinstance(valeurs, pd.DataFrame) or valeurs.empty:
        return
    lignes = []
    for _, r in valeurs.iterrows():
        algo = r["algo"]
        proba = ml_pred.get(f"{algo.lower()}_probability")
        valeur = float(r["valeur_eur"])
        # On relit les leviers de CHAQUE algo : `pareto` ne rend que la porte la
        # plus proche, et les trois lignes afficheraient alors le même levier.
        from src.dashboard.utils.algo_knowledge import split_coach_actions
        titre, _artiste = split_coach_actions(algo, feats)
        premier = next((a for a in titre if a.get("kind") != "smooth"), None)
        lignes.append({
            t("trigger_algo.titre.col_algo", "Algorithme"): _NOMS.get(algo, algo),
            t("trigger_algo.titre.col_chance", "Ta chance"): (
                "—" if proba is None else
                f"{float(proba):.1%}" + (" ≈ plancher"
                                         if sur_le_plancher(algo.lower(), proba) else "")),
            t("trigger_algo.titre.col_worth", "Vaut si ça s'ouvre"):
                f"{valeur:,.0f} €".replace(",", " "),
            t("trigger_algo.titre.col_expect", "Espérance"): (
                "—" if proba is None
                else f"{float(proba) * valeur:,.2f} €".replace(",", " ")),
            t("trigger_algo.titre.col_next", "Prochain levier"): (
                "—" if premier is None
                else f"{premier['label']} · {premier['gap']:,.0f} {premier['unit']}"
                     .replace(",", " ")),
            t("trigger_algo.titre.col_cohort", "Cohorte"): int(r["n"]),
        })
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")

    # ── OÙ METTRE L'EFFORT : la meilleure espérance, nommée ─────────────────
    # Trois lignes de chiffres laissent l'arbitrage au lecteur. Mesuré sur la
    # production : Radio a la MEILLEURE espérance (1,74 €) tout en valant MOINS
    # que Discover Weekly (16 € contre 23 €) — sa chance est plus haute. Une vue
    # qui n'affichait que la porte la plus proche montrait DW et masquait ça.
    esperances = [
        (a, float(ml_pred.get(f"{a.lower()}_probability") or 0) * float(v))
        for a, v in zip(valeurs["algo"], valeurs["valeur_eur"])
        if ml_pred.get(f"{a.lower()}_probability") is not None
    ]
    if esperances:
        meilleur, valeur_max = max(esperances, key=lambda x: x[1])
        st.success(t(
            "trigger_algo.titre.best_bet",
            "🎯 **Meilleure espérance : {algo}** — {val:.2f} €. Ce n'est pas "
            "forcément la porte la plus proche ni la mieux payée : c'est le produit "
            "des deux. À chance égale, vise la plus riche ; à valeur égale, la plus "
            "probable."
        ).format(algo=_NOMS.get(meilleur, meilleur), val=valeur_max))

    st.caption(t(
        "trigger_algo.titre.three_gates_note",
        "La porte la plus PROCHE n'est pas la plus RICHE : Discover Weekly vaut "
        "environ 3,4 fois un Release Radar. « Cohorte » est le nombre de titres sur "
        "lesquels la valeur est mesurée."))


def _valeur_de(valeurs, algo) -> float | None:
    """La valeur € d'un déclenchement pour cet algo, ou `None`.

    `trigger_value` rend `algo, nom, streams_med, valeur_eur, n`. Mesuré au taux
    d'artiste le 2026-09-22 : DW **32,81 €**, Radio 22,11 €, RR 9,71 € — pour des
    cohortes de 104, 239 et 100 titres.
    """
    if algo is None or not isinstance(valeurs, pd.DataFrame) or valeurs.empty:
        return None
    if "algo" not in valeurs.columns or "valeur_eur" not in valeurs.columns:
        return None
    ligne = valeurs[valeurs["algo"] == algo]
    return float(ligne["valeur_eur"].iloc[0]) if not ligne.empty else None


def _render_pareto(leviers: list[dict], valeur_algo: float | None) -> None:
    aff = pd.DataFrame({
        "#": list(range(1, len(leviers) + 1)),
        t("trigger_algo.titre.col_lever", "Levier"): [a["label"] for a in leviers],
        t("trigger_algo.titre.col_now", "Aujourd'hui"): [
            f"{a['current']:,.2f}".replace(",", " ") for a in leviers],
        t("trigger_algo.titre.col_target", "Objectif"): [
            f"{a['target']:,.0f} {a['unit']}".replace(",", " ") for a in leviers],
        t("trigger_algo.titre.col_gap", "Il me manque"): [
            f"{a['gap']:,.0f}".replace(",", " ") for a in leviers],
        t("trigger_algo.titre.col_progress", "Avancement"): [
            min(1.0, max(0.0, a["current"] / a["target"])) if a.get("target") else 0.0
            for a in leviers],
        t("trigger_algo.titre.col_pays", "Ce que ça rapporte"): [
            "—" if a.get("valeur_eur") is None
            else f"+{a['valeur_eur']:,.2f} €".replace(",", " ") for a in leviers],
        t("trigger_algo.titre.col_how", "Comment"): [a["lever"] for a in leviers],
    })
    st.dataframe(
        aff, hide_index=True, width="stretch",
        column_config={
            t("trigger_algo.titre.col_progress", "Avancement"):
                st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
        },
    )
    st.caption(t(
        "trigger_algo.titre.pareto_note",
        "⚠️ **Ce tableau est trié par EFFORT, pas par impact** — le levier le plus "
        "proche de sa cible d'abord. Lis la colonne « ce que ça rapporte » avant de "
        "choisir : mesuré sur ce catalogue, le levier le plus proche s'est déjà "
        "révélé **trente fois moins rentable** que le plus lointain. Les {n} premiers "
        "leviers seulement sont chiffrés — chacun demande de rejouer le modèle."
    ).format(n=LEVIERS_CHIFFRES))


def _render_money_note(valeurs, source_taux: str, eur_stream: float | None) -> None:
    """Ce que les euros disent, et surtout ce qu'ils ne disent pas."""
    with secondary_analyses(t("trigger_algo.titre.money_header",
                              "💶 D'où viennent ces euros")):
        if eur_stream:
            origine = (t("trigger_algo.titre.rate_track", "mesuré sur CE titre")
                       if source_taux == "track"
                       else t("trigger_algo.titre.rate_artist",
                              "moyenne de ton catalogue — ce titre n'a pas encore de "
                              "relevé chez le distributeur"))
            st.caption(t("trigger_algo.titre.rate",
                         "Taux utilisé : **{taux:.6f} € / écoute** ({origine}).")
                       .format(taux=eur_stream, origine=origine))
        if isinstance(valeurs, pd.DataFrame) and not valeurs.empty:
            st.dataframe(valeurs, hide_index=True, width="stretch")
        st.caption(t(
            "trigger_algo.titre.money_caveat",
            "⚠️ **Ce n'est pas le gain d'un déclenchement.** La cohorte de référence "
            "ne contient QUE des titres qui ont déclenché — aucun témoin comparable "
            "qui n'aurait pas déclenché. On en tire un ordre de grandeur, pas un "
            "effet causal. Et une espérance n'est pas une promesse : la moitié des "
            "tirages tombe en dessous."))
        st.caption(t(
            "trigger_algo.titre.no_cost",
            "🚫 **Cette page dit ce qu'une porte VAUT, pas ce qu'elle COÛTE à ouvrir.** "
            "La dépense publicitaire n'est rattachée qu'à 19 titres et s'arrête en "
            "septembre 2024 : un coût par titre calculé là-dessus serait une fiction."))
