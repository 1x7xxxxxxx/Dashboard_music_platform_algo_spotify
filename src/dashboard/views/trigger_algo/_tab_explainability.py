"""trigger_algo — _show_tab_explainability (move-only split)."""
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
import json
import numpy as np
import pandas as pd
import streamlit as st
from ._common import (
    _FEATURE_LABELS,
    _load_xgb_model,
    _show_drift_status,
    _show_imputation_caveat,
    _show_key_factors,
    _show_lime_explanation,
    _show_meta_lever_scoring,
)


def _show_tab_explainability(db, ml_pred, track: str, artist_id):
    st.caption(t(
        "trigger_algo.explain.caption",
        "🔍 **Le pourquoi du score** — quels facteurs poussent ou plombent chaque "
        "probabilité (graphiques SHAP), et le coach qui traduit ça en leviers d'action "
        "concrets. Barres rouges = ça aide le score, bleues = ça le pénalise."
    ))
    if not ml_pred:
        st.info(t("trigger_algo.explain.no_pred",
                  "Aucune prédiction ML disponible pour ce titre. Lancez le DAG `ml_scoring_daily`."))
        return

    features_json = ml_pred.get("features_json")
    if not features_json:
        st.warning(t("trigger_algo.explain.no_features", "features_json absent de la prédiction ML."))
        _show_key_factors(None)
        return

    try:
        feats = json.loads(features_json) if isinstance(features_json, str) else features_json
    except Exception:
        st.warning(t("trigger_algo.explain.parse_failed", "Impossible de parser features_json."))
        return

    try:
        from src.utils.ml_inference import FEATURE_COLUMNS
    except Exception as e:
        st.warning(t("trigger_algo.explain.inference_unavailable",
                     "ml_inference non disponible : {err}").format(err=e))
        _show_key_factors(features_json)
        return

    _show_imputation_caveat(feats, FEATURE_COLUMNS)
    _show_drift_status(feats)

    _calib = ak.calibration_note("DW", ml_pred.get("dw_probability"))
    if _calib:
        st.info(t("trigger_algo.explain.calib_note",
                  "📖 Lecture des probabilités (modèle non calibré) : {note}").format(note=_calib))

    try:
        import shap
        import matplotlib
        try:
            matplotlib.use("Agg")
        except Exception:
            pass
        import matplotlib.pyplot as plt
        _shap_available = True
    except ImportError:
        _shap_available = False

    if not _shap_available:
        st.warning(t(
            "trigger_algo.explain.shap_missing",
            "Bibliothèque `shap` non installée. Ajoutez `shap>=0.44.0` dans requirements.txt "
            "puis reconstruisez l'image Docker (`docker-compose build && docker-compose up -d`)."
        ))
    else:
        X_df = pd.DataFrame(
            [[float(feats.get(f, 0.0)) for f in FEATURE_COLUMNS]],
            columns=FEATURE_COLUMNS
        )
        for model_key, algo_label in [
            ("dw_classifier", "Discover Weekly"),
            ("rr_classifier", "Release Radar"),
        ]:
            with st.expander(t("trigger_algo.explain.shap_waterfall",
                               "🔍 SHAP Waterfall — {algo}").format(algo=algo_label),
                             expanded=(model_key == "dw_classifier")):
                model = _load_xgb_model(model_key)
                if model is None:
                    st.warning(t("trigger_algo.explain.model_not_found",
                                 "Modèle `{key}` introuvable dans machine_learning/mlruns/.")
                               .format(key=model_key))
                    continue
                try:
                    explainer = shap.TreeExplainer(model)
                    shap_exp = explainer(X_df)
                    shap.plots.waterfall(shap_exp[0], max_display=13, show=False)
                    st.pyplot(plt.gcf(), clear_figure=True)
                    st.caption(t(
                        "trigger_algo.explain.shap_logodds_caption",
                        "Valeurs SHAP en espace log-odds (modèle non calibré). "
                        "Barres rouges = contribution positive au score, bleues = négative."
                    ))
                except Exception as e:
                    st.warning(t("trigger_algo.explain.shap_error",
                                 "SHAP {algo} : {err}").format(algo=algo_label, err=e))

        # Regressor (volume) waterfall + natural-language autopsy. The forecast is a
        # FLOOR: its SHAP "receipt" explains why the conservative volume is what it is.
        with st.expander(t("trigger_algo.explain.dw_autopsy",
                           "🧾 Autopsie du VOLUME prédit (régresseur DW) — plancher"),
                         expanded=False):
            ml_widgets.render_regressor_badge("DW")
            reg = _load_xgb_model("dw_regressor")
            if reg is None:
                st.warning(t("trigger_algo.explain.dw_reg_not_found",
                             "Modèle `dw_regressor` introuvable dans machine_learning/mlruns/."))
            else:
                try:
                    reg_explainer = shap.TreeExplainer(reg)
                    reg_exp = reg_explainer(X_df)
                    shap.plots.waterfall(reg_exp[0], max_display=13, show=False)
                    st.pyplot(plt.gcf(), clear_figure=True)
                    baseline = float(np.ravel(reg_exp[0].base_values)[0])
                    values = [float(v) for v in np.ravel(reg_exp[0].values)]
                    prediction = baseline + sum(values)
                    contributions = [
                        {"label": _FEATURE_LABELS.get(col, (col, True))[0], "value": values[i]}
                        for i, col in enumerate(FEATURE_COLUMNS) if i < len(values)
                    ]
                    ml_widgets.render_shap_narrative(
                        t("trigger_algo.explain.dw_volume_label", "Discover Weekly (volume)"),
                        baseline, max(0.0, prediction), contributions)
                    st.caption(t("trigger_algo.explain.dw_shap_caption",
                                 "Valeurs SHAP en streams 7j. À lire comme un plancher : "
                                 "le régresseur sous-estime les hits (voir badge ci-dessus)."))
                except Exception as e:
                    st.warning(t("trigger_algo.explain.dw_shap_error",
                                 "SHAP régresseur DW : {err}").format(err=e))

        # Radio volume regressor (MLflow exp 6) — same floor reading. Recent fuel
        # dominates; quality signals (saves, playlist adds) go flat for volume.
        with st.expander(t("trigger_algo.explain.radio_autopsy",
                           "🧾 Autopsie du VOLUME Radio prédit (régresseur) — plancher"),
                         expanded=False):
            ml_widgets.render_regressor_badge("RADIO")
            reg = _load_xgb_model("radio_regressor")
            if reg is None:
                st.warning(t("trigger_algo.explain.radio_reg_not_found",
                             "Modèle `radio_regressor` introuvable dans machine_learning/mlruns/."))
            else:
                try:
                    reg_explainer = shap.TreeExplainer(reg)
                    reg_exp = reg_explainer(X_df)
                    shap.plots.waterfall(reg_exp[0], max_display=13, show=False)
                    st.pyplot(plt.gcf(), clear_figure=True)
                    baseline = float(np.ravel(reg_exp[0].base_values)[0])
                    values = [float(v) for v in np.ravel(reg_exp[0].values)]
                    prediction = baseline + sum(values)
                    contributions = [
                        {"label": _FEATURE_LABELS.get(col, (col, True))[0], "value": values[i]}
                        for i, col in enumerate(FEATURE_COLUMNS) if i < len(values)
                    ]
                    ml_widgets.render_shap_narrative(
                        t("trigger_algo.explain.radio_volume_label", "Radio (volume)"),
                        baseline, max(0.0, prediction), contributions)
                    st.caption(t("trigger_algo.explain.radio_shap_caption",
                                 "Valeurs SHAP en streams 7j. Le carburant récent domine ; "
                                 "saves/playlists sont plats sur le volume (voir badge)."))
                except Exception as e:
                    st.warning(t("trigger_algo.explain.radio_shap_error",
                                 "SHAP régresseur Radio : {err}").format(err=e))

    st.markdown("---")
    st.subheader(t("trigger_algo.explain.coach_header",
                   "🧭 Coach & curseurs de décision par algorithme"))
    for _algo in ak.populated_algos():
        st.markdown(f"### {ak.ALGO_LABELS.get(_algo, _algo)}")
        ml_widgets.render_coach(_algo, feats)
        # DW is the lever model (forecast.md §5): show the local marginal payoff of a lever.
        if _algo == "DW":
            ml_widgets.render_lever_sensitivity(_algo, feats)
        ml_widgets.render_feature_gauges(_algo, feats)
        if _algo in ak.volume_algos():
            ml_widgets.render_volume_gauges(_algo, feats)
        if _algo == "RADIO":
            _recovery = ak.radio_discovery_recovery_note(feats)
            if _recovery:
                st.warning(_recovery)
        st.markdown("---")
    _show_key_factors(features_json)
    _show_lime_explanation(ml_pred)
    _show_meta_lever_scoring(db, track, artist_id)
