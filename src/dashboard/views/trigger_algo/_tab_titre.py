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
from src.dashboard.utils.formats import eur, num
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import secondary_analyses

from src.dashboard.utils import charts
from src.dashboard.utils.algo_preview_data import (
    budget_fourchette, format_proba, lire_cpr_bornes, proba_affichable, texte_plancher)
from src.dashboard.utils.semantic_colors import ATTENTION, BON
from src.dashboard.utils.algo_knowledge import nearest_gate
from ._pareto import pareto

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
    # R263 — ONE `pareto` call (it was two: the first only to learn the algorithm, and
    # each call replays the model twice per lever). The gate is known without the model.
    porte = nearest_gate(feats)
    plan = (pareto(feats, valeur_porte=_valeur_de(valeurs, porte["algo"]))
            if porte else None)
    if not plan:
        st.success(t("trigger_algo.titre.nothing_left",
                     "✅ Aucune métrique mesurée de ce titre n'est sous son objectif. "
                     "Rien à corriger ici — regarde l'onglet **Où en sont mes titres** "
                     "pour savoir lequel pousser."))
        return

    algo = plan["algo"]
    valeur_algo = _valeur_de(valeurs, algo)

    # ── L'en-tête : la porte, sa valeur, l'espérance ─────────────────────────
    proba = proba_affichable(algo.lower(), ml_pred.get(f"{algo.lower()}_probability"))
    c1, c2, c3 = st.columns(3)
    c1.metric(t("trigger_algo.titre.tile_gate", "Porte la plus proche"), _NOMS.get(algo, algo))
    if valeur_algo:
        c2.metric(t("trigger_algo.titre.tile_value", "Ce que ça vaut si ça s'ouvre"),
                  eur(valeur_algo, 0))
        # REFUSE, not mark (2026-09-26): an expected value computed from a floor
        # probability is the calibration intercept times a price — not a forecast.
        c3.metric(t("trigger_algo.titre.tile_expect", "Espérance aujourd'hui"),
                  (eur(proba * valeur_algo, 2)
                   if proba is not None else texte_plancher()))

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

    # R381 (V56, V64, V66) — playlist by playlist: what weighs, where the title stands
    # against the entry threshold, and the cost range to close the gap.
    from ._playlist_detail import render_ce_qui_pese
    render_ce_qui_pese(db, track, artist_id, ml_pred, feats)

    # ── Le Pareto ────────────────────────────────────────────────────────────
    st.subheader(t("trigger_algo.titre.pareto_header", "🪜 Ce qu'il te reste à faire"))
    _render_pareto(db, artist_id, plan["leviers"])

    _render_money_note(valeurs, source_taux, eur_stream)


def _render_trois_portes(valeurs, ml_pred: dict, feats: dict) -> None:
    """Les trois algos en regard : chance, valeur, espérance, et ce qui manque.

    C'est la réponse à « l'équivalent en argent pour déclencher CHAQUE algo ». Une
    seule porte affichée laisserait croire que la plus proche est la plus
    intéressante — ce que la mesure dément : Discover Weekly vaut **3,4 fois** un
    Release Radar, et c'est souvent la porte la plus lointaine.

    ⚠️ La colonne « chance » REFUSE une probabilité au plancher (score brut
    négligeable) et écrit « pas d'estimation fiable » — même règle que l'aperçu
    (2026-09-26, porte commune `proba_affichable`). L'espérance aussi : un plancher
    multiplié par une valeur n'est pas une espérance.
    """
    if not isinstance(valeurs, pd.DataFrame) or valeurs.empty:
        return
    _pastilles(valeurs, ml_pred)

    # ── OÙ METTRE L'EFFORT : la meilleure espérance, nommée ─────────────────
    # Trois lignes de chiffres laissent l'arbitrage au lecteur. Mesuré sur la
    # production : Radio a la MEILLEURE espérance (1,74 €) tout en valant MOINS
    # que Discover Weekly (16 € contre 23 €) — sa chance est plus haute. Une vue
    # qui n'affichait que la porte la plus proche montrait DW et masquait ça.
    # Only OFF-floor probabilities enter the argmax (2026-09-26): among three
    # floors, « meilleure espérance » named the algo with the highest intercept.
    esperances = [
        (a, p * float(v))
        for a, v in zip(valeurs["algo"], valeurs["valeur_eur"])
        if (p := proba_affichable(a.lower(), ml_pred.get(f"{a.lower()}_probability")))
        is not None
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


def _pastilles(valeurs: pd.DataFrame, ml_pred: dict) -> None:
    """R404 (V61): each playlist in a small readable box, coloured by its chance.

    The bands are the guide's (STOP < 20 % ≤ OPTIMISER < 50 % ≤ SCALER); a floor
    probability is grey and says so — the same refusal as the table below.
    """
    cols = st.columns(len(valeurs))
    for col, algo in zip(cols, valeurs["algo"]):
        raw = ml_pred.get(f"{algo.lower()}_probability")
        proba = proba_affichable(algo.lower(), raw)
        couleur = ("gray" if proba is None else "green" if proba >= 0.5
                   else "orange" if proba >= 0.2 else "red")
        with col:
            st.badge(f"{_NOMS.get(algo, algo)} · {format_proba(algo.lower(), raw, decimals=0)}",
                     color=couleur)


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


def pareto_figure(leviers: list[dict]):
    """R477 (W14) — the levers as bars: how far each one is from its target. Pure.

    Effort order, the closest on top — the order the coach ranks them in. The text on
    each bar is what is still missing and, when the model was replayed for it, what
    closing it is worth: the « ce que ça rapporte » column the table carried, which
    is what makes the effort order contestable.
    """
    import plotly.graph_objects as go

    rows = list(reversed(leviers))
    progress = [min(1.0, max(0.0, a["current"] / a["target"])) if a.get("target") else 0.0
                for a in rows]
    def _gap(a: dict) -> str:
        g = float(a["gap"] or 0)
        # A ratio gap (0.16) rounded to 0 decimals read « il manque 0 ratio » on the PNG.
        return num(g, 2 if abs(g) < 10 else 0)

    text = [(t("trigger_algo.titre.bar_done", "✓ objectif atteint") if p >= 1 else
             t("trigger_algo.titre.bar_gap", "il manque {gap} {unit}")
             .format(gap=_gap(a), unit=a["unit"])
             + ("" if (a.get("valeur_eur") or 0) < 0.5 else f" · +{eur(a['valeur_eur'], 0)}"))
            for a, p in zip(rows, progress)]
    labels = [a["label"] for a in rows]
    # Done in colour, the missing part in grey on the same bar : the gap IS the reading.
    fig = go.Figure([
        go.Bar(x=progress, y=labels, orientation="h",
               marker_color=[BON if p >= 1 else ATTENTION for p in progress],
               hovertemplate="%{y}<br>%{x:.0%}<extra></extra>", showlegend=False),
        go.Bar(x=[1 - p for p in progress], y=labels, orientation="h", text=text,
               textposition="inside", insidetextanchor="end", marker_color="rgba(128,128,128,0.18)",
               hoverinfo="skip", showlegend=False)])
    fig.update_layout(barmode="stack")
    fig.update_xaxes(range=[0, 1.02], tickformat=".0%",
                     title=t("trigger_algo.titre.bar_axis", "Avancement vers l'objectif"))
    fig.update_yaxes(automargin=True)
    fig.update_layout(height=80 + 46 * len(rows), margin=dict(t=20, l=10, r=10, b=40))
    return fig


def streams_gap(leviers: list[dict]) -> float | None:
    """The 7-day streams still missing — the only lever Meta Ads can buy. Pure."""
    lev = next((a for a in leviers if a.get("feature") == "StreamsLast7Days"), None)
    return float(lev["gap"]) if lev and lev.get("gap") else None


def _render_pareto(db, artist_id, leviers: list[dict]) -> None:
    charts.plotly_chart(pareto_figure(leviers), width="stretch")
    # W14 « lier à ce que ça coûterait en Meta Ads au meilleur CPR et au CPR moyen,
    # sans tableaux » — one tile, one formula (`budget_fourchette`, R372) : the first
    # screen of this section is capped at 5 gauges (first-screen-ceilings.json).
    cout = budget_fourchette(streams_gap(leviers), lire_cpr_bornes(db, artist_id))
    if cout:
        st.metric(t("trigger_algo.titre.cost_range",
                    "En Meta Ads, du meilleur CPR au CPR moyen"),
                  f"{eur(cout[0], 0)} → {eur(cout[1], 0)}")


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
