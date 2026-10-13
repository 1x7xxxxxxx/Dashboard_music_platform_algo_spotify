"""🔬 Par playlist : ce qui pèse (R381 ; le seuil et son coût sont partis avec R559).

Type: Sub
Uses: streamlit, plotly, src.utils.shap_explain, src.dashboard.utils.algo_preview_data
Depends on: ml_song_predictions (reçue du routeur)
Triggers: views/trigger_algo/_tab_titre.py, views/trigger_algo/router.py
Persists in: nothing

Notes vocales V56, V64, V66, V71 (2026-10-05). Quatre réponses, chacune lue à UNE source :

  - ce qui pèse : les contributions SHAP de chaque classifieur, triées par poids
    décroissant, DW → Radio → RR (`ALGO_ORDER`). Une playlist dont la probabilité est
    au plancher (`proba_affichable` → None) est EXCLUE : expliquer un intercept de
    calibration, c'est expliquer du bruit. Un critère absent de `features_json` est
    marqué « manquant » — le modèle l'a lu comme 0 (`ml_inference`, même remplissage) ;
  - où j'en suis et ce que coûterait l'écart : RETIRÉS le 2026-10-13 (R559, fiche 56,
    « redondant avec la 46 ») — les jauges du catalogue les portent ;
  - les recommandations détaillées de la dernière sortie : celles du CPR Optimizer,
    RÉUTILISÉES (`meta_cpr_optimizer.recommendations`), pas recalculées.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils import charts
from src.dashboard.utils.algo_preview_data import proba_affichable
from src.dashboard.utils.i18n import t
from src.dashboard.utils.semantic_colors import BON, MAUVAIS
from src.utils.algo_order import named_algos

from ._common._explain import _FEATURE_LABELS
from ._common._loaders import _load_xgb_model

#: Criteria shown per playlist — the rest of the 13 weigh less than the eighth.
TOP = 8

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


def render_ce_qui_pese(ml_pred: dict, feats: dict) -> None:
    """V56/V64 — what weighs, playlist by playlist, for the selected title.

    R559 (fiche 56, owner 2026-10-13 : « je ne comprends pas le graphique, redondant avec
    la 46 ») — the threshold bars and their shared cost left: the catalogue's gauges now
    carry the 28-day figures and the price of the gap."""
    st.subheader(t("trigger_algo.detail.header", "🔬 Playlist par playlist"))
    shown, floored = shap_par_playlist(feats, ml_pred)
    if shown:
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
