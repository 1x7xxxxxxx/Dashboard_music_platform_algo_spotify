"""🔬 Par playlist : ce qui pèse, où j'en suis, ce que coûterait l'écart (R381).

Type: Sub
Uses: streamlit, plotly, src.utils.shap_explain, src.utils.ml_outcome_labeling,
  src.dashboard.utils.algo_preview_data, views.meta_cpr_optimizer
Depends on: s4a_song_algo_outcomes, v_meta_campaign_daily, campaign_track_mapping,
  ml_song_predictions (reçue du routeur)
Triggers: views/trigger_algo/_tab_titre.py, views/trigger_algo/router.py
Persists in: nothing

Notes vocales V56, V64, V66, V71 (2026-10-05). Quatre réponses, chacune lue à UNE source :

  - ce qui pèse : les contributions SHAP de chaque classifieur, triées par poids
    décroissant, DW → Radio → RR (`ALGO_ORDER`). Une playlist dont la probabilité est
    au plancher (`proba_affichable` → None) est EXCLUE : expliquer un intercept de
    calibration, c'est expliquer du bruit. Un critère absent de `features_json` est
    marqué « manquant » — le modèle l'a lu comme 0 (`ml_inference`, même remplissage) ;
  - où j'en suis : les streams algo réalisés sur 28 jours contre le seuil d'ENTRÉE,
    `TARGET_THRESHOLDS` et lui seul — le seuil qui étiquette l'entraînement ;
  - ce que coûterait l'écart : une FOURCHETTE meilleur CPR ↔ CPR moyen
    (`budget_fourchette`), dite « ordre de grandeur », jamais un devis ;
  - les recommandations détaillées de la dernière sortie : celles du CPR Optimizer,
    RÉUTILISÉES (`meta_cpr_optimizer.recommendations`), pas recalculées.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils import charts
from src.dashboard.utils.algo_preview_data import (
    budget_fourchette, budget_par_porte, lire_cpr_bornes, proba_affichable)
from src.dashboard.utils.formats import eur
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import disclosure_caption
from src.dashboard.utils.semantic_colors import BON, MAUVAIS
from src.utils.algo_order import named_algos
from src.utils.artist_name_filter import ARTIST_NAME_LIKE
from src.utils.ml_outcome_labeling import TARGET_THRESHOLDS

from ._common._explain import _FEATURE_LABELS
from ._common._loaders import _load_xgb_model

#: Criteria shown per playlist — the rest of the 13 weigh less than the eighth.
TOP = 8

_Q_OUTCOME = """
SELECT dw_streams, rr_streams, radio_streams, recorded_at
  FROM s4a_song_algo_outcomes
 WHERE artist_id = %s AND song = %s AND time_window = '28d' AND song NOT ILIKE %s
 ORDER BY recorded_at DESC LIMIT 1
"""


def _label(feature: str) -> str:
    """The criterion's name as the rest of the page says it — never the column name."""
    return t(f"algo.label.{feature}", _FEATURE_LABELS.get(feature, (feature, True))[0])


def shap_par_playlist(feats: dict, ml_pred: dict, loader=_load_xgb_model,
                      top: int = TOP) -> tuple[list[dict], list[str]]:
    """(explained playlists, playlists left out at the floor). Pure but for the loader.

    Each explained playlist: `algo`, `name`, `proba`, and `contribs` — the `top`
    criteria by |SHAP| DECREASING, each with `feature`, `label`, `shap`, `missing`.
    """
    from src.utils.ml_inference import FEATURE_COLUMNS
    from src.utils.shap_explain import explain

    feats = feats or {}
    X = pd.DataFrame([[float(feats.get(f, 0.0) or 0.0) for f in FEATURE_COLUMNS]],
                     columns=FEATURE_COLUMNS)
    shown, floored = [], []
    for algo, name in named_algos():
        proba = proba_affichable(algo.lower(), (ml_pred or {}).get(f"{algo.lower()}_probability"))
        if proba is None:
            floored.append(name)
            continue
        model = loader(f"{algo.lower()}_classifier")
        if model is None:
            continue
        values = explain(model, X).values[0]
        order = sorted(range(len(FEATURE_COLUMNS)), key=lambda i: -abs(values[i]))[:top]
        shown.append({"algo": algo, "name": name, "proba": proba, "contribs": [
            {"feature": FEATURE_COLUMNS[i], "label": _label(FEATURE_COLUMNS[i]),
             "shap": float(values[i]), "missing": FEATURE_COLUMNS[i] not in feats}
            for i in order]})
    return shown, floored


def seuils_atteints(outcome: dict | None) -> list[dict]:
    """Per playlist, DW → Radio → RR: realized 28-day streams vs the ENTRY threshold. Pure.

    `reached` is None when nothing was entered — absent is not 0. The comparison is
    STRICT (`>`), as `ml_outcome_labeling.bin_label` labels the training set.
    """
    out = []
    for algo, name in named_algos():
        seuil = TARGET_THRESHOLDS[algo.lower()]
        val = (outcome or {}).get(f"{algo.lower()}_streams")
        val = None if val is None or pd.isna(val) else float(val)
        out.append({"algo": algo, "name": name, "threshold": seuil, "reached": val,
                    "entered": val is not None and val > seuil})
    return out


def cout_commun(fourchettes: list) -> tuple[float, float] | None:
    """The range all playlists share, or None. Pure.

    The gap is the coach's 7-day streams lever, so the three ranges are usually the
    same one: printed on three lines, it reads as three budgets to add up.
    """
    return fourchettes[0] if fourchettes and fourchettes[0] and len(set(fourchettes)) == 1 else None


def _figure(shown: list[dict]):
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    # Stacked, one playlist per row: side by side, the criteria names of one
    # panel ran over the bars of the next (seen on the PNG, 2026-10-05).
    fig = make_subplots(rows=len(shown), cols=1, vertical_spacing=0.12,
                        subplot_titles=[f"{s['name']} · {s['proba']:.0%}" for s in shown])
    for row, s in enumerate(shown, start=1):
        rows = list(reversed(s["contribs"]))            # the heaviest on top
        fig.add_trace(go.Bar(
            x=[r["shap"] for r in rows], orientation="h",
            y=[r["label"] + (" ⚠ manquant" if r["missing"] else "") for r in rows],
            marker_color=[BON if r["shap"] > 0 else MAUVAIS for r in rows],
            hovertemplate="%{y}<br>%{x:+.3f}<extra></extra>", showlegend=False),
            row=row, col=1)
    fig.update_yaxes(automargin=True)
    fig.update_layout(height=len(shown) * (40 + 26 * TOP),
                      margin=dict(t=40, l=10, r=10, b=20))
    return fig


def render_ce_qui_pese(db, track: str, artist_id, ml_pred: dict, feats: dict) -> None:
    """V56/V64/V66 — the three answers for the selected title, without a table."""
    st.subheader(t("trigger_algo.detail.header", "🔬 Playlist par playlist"))
    shown, floored = shap_par_playlist(feats, ml_pred)
    if shown:
        st.markdown(t("trigger_algo.detail.shap_head",
                      "**Ce qui pèse le plus**, du critère le plus lourd au plus léger. "
                      "Vert : il pousse vers la playlist ; rouge : il retient."))
        charts.plotly_chart(_figure(shown), width="stretch")
    if floored:
        st.caption(t("trigger_algo.detail.shap_floor",
                     "Pas d'explication pour {names} : le modèle n'y distingue pas ce "
                     "titre (probabilité au plancher) — détailler ce qu'il ne dit pas "
                     "n'apprendrait rien.").format(names=", ".join(floored)))
    if any(c["missing"] for s in shown for c in s["contribs"]):
        st.warning(t("trigger_algo.detail.missing",
                     "⚠ **Critère manquant** : la donnée n'a pas été reçue, le modèle l'a "
                     "lue comme 0. Dépose tes CSV Spotify for Artists pour la remplir."))

    rows = db.fetch_query(_Q_OUTCOME, (artist_id, track, ARTIST_NAME_LIKE)) if artist_id else []
    outcome = (dict(zip(("dw_streams", "rr_streams", "radio_streams"), rows[0][:3]))
               if rows else None)
    bornes = lire_cpr_bornes(db, artist_id)
    gaps = {g["algo"]: g["gap"] for g in budget_par_porte(feats, None)}
    seuils = seuils_atteints(outcome)
    fourchettes = [budget_fourchette(gaps.get(s["algo"]), bornes) for s in seuils]
    commune = cout_commun(fourchettes)
    for s, f in zip(seuils, fourchettes):
        st.markdown(_ligne(s, None if commune else f))
    if commune:
        # One shared lever (the 7-day streams): one budget, never three to add up.
        st.markdown(t("trigger_algo.detail.cost_shared",
                      "Les {n} playlists demandent **la même chose** : combler l'écart "
                      "coûte **{lo} à {hi}** — un seul budget, pas trois.").format(
                          n=len(seuils), lo=eur(commune[0], 0), hi=eur(commune[1], 0)))
    st.caption(t("trigger_algo.detail.cost_note",
                 "Seuil d'entrée : les streams algo sur 28 jours au-delà desquels un titre "
                 "compte comme entré (le seuil d'entraînement du modèle). Coût : l'écart "
                 "de streams sur 7 jours × ton meilleur CPR ↔ ton CPR moyen — un "
                 "**ordre de grandeur**, qui suppose qu'un clic vaut une écoute."))
    st.caption(disclosure_caption())


def _ligne(s: dict, fourchette: tuple[float, float] | None) -> str:
    if s["reached"] is None:
        etat = t("trigger_algo.detail.not_entered",
                 "réalisé : pas encore saisi (plus bas, « Ce qui s'est vraiment passé »)")
    else:
        etat = t("trigger_algo.detail.reached", "réalisé **{v:,.0f}** / seuil {s}").format(
            v=s["reached"], s=s["threshold"]).replace(",", " ")
        etat += " ✅" if s["entered"] else ""
    cout = ("" if fourchette is None else " · " + t(
        "trigger_algo.detail.cost", "combler l'écart : **{lo} à {hi}**").format(
            lo=eur(fourchette[0], 0), hi=eur(fourchette[1], 0)))
    return f"- **{s['name']}** — {etat}{cout}"


def render_recos_derniere_sortie(db, artist_id) -> None:
    """V71 — the CPR Optimizer's detailed recommendations, for the latest release."""
    from src.dashboard.utils.algo_preview_data import budget_declenchement
    from src.dashboard.views.meta_cpr_optimizer import (
        for_track, recommendations, render_cards)

    sortie = (budget_declenchement(db, artist_id) or {}).get("song")
    if not sortie:
        return
    recos = for_track(recommendations(db, artist_id), sortie)
    st.markdown(t("trigger_algo.detail.recos_head",
                  "**🃏 Recommandations détaillées — {song}** (ta dernière sortie)")
                .format(song=sortie))
    if recos.empty:
        st.caption(t("trigger_algo.detail.recos_none",
                     "Aucune campagne reliée à ce titre — relie-la dans 🔗 Mapping "
                     "cross-plateforme pour obtenir une recommandation."))
        return
    render_cards(recos)
