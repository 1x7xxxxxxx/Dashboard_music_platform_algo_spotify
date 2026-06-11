"""trigger_algo explain — move-only split of _common."""
from src.dashboard.utils.i18n import t
import json
import numpy as np
import pandas as pd
import streamlit as st


_FEATURE_LABELS = {
    "StreamsLast7Days_log": ("Streams 7 derniers jours", True),
    "CurrentSpotifyFollowers_log": ("Followers Spotify", True),
    "HowManySongsHasThisArtistEverReleased": ("Taille du catalogue", True),
    "DaysSinceRelease": ("Jours depuis la sortie", False),
    "ListenersStreamRatio28Days_adj": ("Ratio auditeurs/streams (fidélité)", True),
    "Velocity_Streams": ("Vélocité (accélération streams)", True),
    "ReleasePhaseEarly": ("Phase de sortie récente (< 30j)", True),
    "ReleaseConsistencyNum": ("Régularité des sorties", True),
    "HowManySongsDoYouHaveInRadioRightNow": ("Chansons en Radio en ce moment", True),
    "IsThisSongOptedIntoSpotifyDiscoveryMode": ("Discovery Mode activé", True),
    "NonAlgoStreams28Days_log": ("Streams non-algo (28j)", True),
    "SavesLast28Days_adj": ("Saves (28j)", True),
    "PlaylistAddsLast28Days_adj": ("Ajouts playlist (28j)", True),
}


_MARKETING_ACTIONS = {
    "StreamsLast7Days_log":
        "Boost week-1 streams via Groover/Fluence playlist submissions this week.",
    "CurrentSpotifyFollowers_log":
        "Run a follower-acquisition campaign: Meta Ads → Spotify follow link.",
    "HowManySongsHasThisArtistEverReleased":
        "Release more tracks — catalogue depth signals artist maturity to the algorithm.",
    "DaysSinceRelease":
        "Act now — you are still in the critical J+28 window. Submit to curators immediately.",
    "ListenersStreamRatio28Days_adj":
        "Encourage repeat plays: include CTA 'Save to library' in Stories and posts.",
    "Velocity_Streams":
        "Coordinate a stream spike: synchronise release push across all channels on the same day.",
    "ReleasePhaseEarly":
        "Track is past early phase — shift strategy to long-tail (editorial pitch, sync licensing).",
    "ReleaseConsistencyNum":
        "Maintain a release cadence of every 4–6 weeks minimum to signal consistency.",
    "HowManySongsDoYouHaveInRadioRightNow":
        "Opt existing tracks into Spotify Discovery Mode to increase radio eligibility.",
    "IsThisSongOptedIntoSpotifyDiscoveryMode":
        "Enable Discovery Mode for this track in Spotify for Artists dashboard.",
    "NonAlgoStreams28Days_log":
        "Drive non-algo streams: email list, YouTube premiere, TikTok, social posts.",
    "SavesLast28Days_adj":
        "Add a 'Save this track' CTA to every post — saves are one of the strongest DW signals.",
    "PlaylistAddsLast28Days_adj":
        "Pitch curators via Spotify for Artists + Groover to increase playlist adds.",
}


_IMPUTED_FEATURES = {
    "HowManySongsDoYouHaveInRadioRightNow",
    "IsThisSongOptedIntoSpotifyDiscoveryMode",
    "NonAlgoStreams28Days_log",
}


def _show_key_factors(features_json):
    if not features_json:
        return
    try:
        feats = json.loads(features_json) if isinstance(features_json, str) else features_json
    except Exception:
        return
    items = []
    for key, (label, high_is_good) in _FEATURE_LABELS.items():
        if key not in feats:
            continue
        label = t(f"algo.label.{key}", label)
        val = float(feats[key])
        is_positive = (val > 0.5 and high_is_good) or (val <= 0.5 and not high_is_good)
        if "_log" in key:
            display = f"{int(np.expm1(val)):,}"
        elif key == "DaysSinceRelease":
            display = f"{int(val)} jours"
        elif key in ("ReleasePhaseEarly", "IsThisSongOptedIntoSpotifyDiscoveryMode"):
            display = "Oui" if val >= 0.5 else "Non"
        else:
            display = f"{val:.2f}"
        items.append({"key": key, "label": label, "display": display,
                      "is_positive": is_positive, "val": abs(val)})
    positives = sorted([i for i in items if i["is_positive"]], key=lambda x: x["val"], reverse=True)
    negatives = sorted([i for i in items if not i["is_positive"]], key=lambda x: x["val"], reverse=True)
    st.subheader(t("trigger_algo.common.key_factors_header", "🔍 Facteurs clés & leviers marketing"))
    col1, col2 = st.columns(2)
    with col1:
        st.write(t("trigger_algo.common.strengths_header", "**✅ Points forts**"))
        for item in positives[:3]:
            st.success(f"**{item['label']}** : {item['display']}")
        if not positives:
            st.caption(t("trigger_algo.common.no_positive", "Aucun facteur positif détecté."))
    with col2:
        st.write(t("trigger_algo.common.improve_header",
                   "**⚠️ Points à améliorer — actions recommandées**"))
        for item in negatives[:3]:
            st.warning(f"**{item['label']}** : {item['display']}")
            action = _MARKETING_ACTIONS.get(item["key"])
            if action:
                st.caption(f"→ {action}")
        if not negatives:
            st.caption(t("trigger_algo.common.no_negative", "Aucun facteur négatif détecté."))


_DM_KEY = "IsThisSongOptedIntoSpotifyDiscoveryMode"


def _show_imputation_caveat(feats: dict, feature_columns) -> None:
    """Warn which model inputs are imputed/absent → probabilities are indicative."""
    missing = [f for f in feature_columns if f not in feats]
    zeroed = [f for f in feature_columns
              if f in feats and f in _IMPUTED_FEATURES and float(feats.get(f, 0.0)) == 0.0]
    flagged = set(missing) | set(zeroed)
    # Manual-source features (migration 052): a value the tenant entered — even a
    # genuine 0 — is real data, not imputation. Drop it from the warning when known.
    dm_known = bool(feats.get("discovery_mode_known"))
    nonalgo_known = bool(feats.get("nonalgo_known"))
    radio_known = bool(feats.get("radio_known"))
    if dm_known:
        flagged.discard(_DM_KEY)
    if nonalgo_known:
        flagged.discard("NonAlgoStreams28Days_log")
    if radio_known:
        flagged.discard("HowManySongsDoYouHaveInRadioRightNow")
    if flagged:
        labels = [t(f"algo.label.{f}", _FEATURE_LABELS.get(f, (f, True))[0])
                  for f in sorted(flagged)]
        st.warning(t(
            "trigger_algo.common.imputation_warning",
            "⚠️ **{n}/{total} variables imputées à 0/neutre** "
            "faute de données S4A : les probabilités sont **indicatives, non calibrées** "
            "(comparaison relative entre titres, pas une probabilité absolue).\n\n"
            "Variables concernées : {labels}."
        ).format(n=len(flagged), total=len(feature_columns), labels=", ".join(labels)))
    if not dm_known:
        st.caption(t("trigger_algo.common.dm_unknown",
                     "ℹ️ **Discovery Mode non renseigné** pour ce titre → traité comme "
                     "désactivé (peut fausser DW/Radio). Saisissez-le dans l'onglet "
                     "« 🎯 Vue Globale » pour fiabiliser le score."))
    else:
        opted = float(feats.get(_DM_KEY, 0.0)) >= 0.5
        _state = (t("trigger_algo.common.dm_on", "activé") if opted
                  else t("trigger_algo.common.dm_off", "désactivé"))
        st.caption(t("trigger_algo.common.dm_known",
                     "✅ Discovery Mode renseigné : **{state}** (donnée réelle, non imputée).")
                   .format(state=_state))
    _entered = []
    if nonalgo_known:
        _entered.append(t("algo.label.NonAlgoStreams28Days", "Streams non-algo (28j)"))
    if radio_known:
        _entered.append(t("algo.label.HowManySongsDoYouHaveInRadioRightNow", "Titres en Radio"))
    if _entered:
        st.caption(t("trigger_algo.common.manual_entered",
                     "✅ Saisies S4A prises en compte : **{names}** (données réelles, non imputées).")
                   .format(names=", ".join(_entered)))


def _show_drift_status(feats: dict) -> None:
    """Flag features outside the training envelope (|z|>4) → unreliable prediction."""
    try:
        from src.utils.ml_inference import check_drift
    except Exception:
        return
    drifted = check_drift(feats or {})
    if drifted:
        st.warning(t(
            "trigger_algo.common.drift_detected",
            "📉 **Drift détecté** : {n} variable(s) hors de l'enveloppe "
            "d'entraînement (|z| > 4) — {vars}. La prédiction extrapole "
            "et est moins fiable pour ce titre."
        ).format(n=len(drifted), vars=', '.join(drifted)))
    else:
        st.caption(t("trigger_algo.common.drift_none",
                     "📉 Drift : toutes les variables sont dans l'enveloppe d'entraînement."))


def _show_lime_explanation(ml_pred: dict | None) -> None:
    """Local LIME explanation for the current track's DW prediction.

    Complements the SHAP waterfall with an alternative local view (perturbation-based
    instead of game-theoretic). Graceful fallback if `lime` or the background sample
    is unavailable.
    """
    if not ml_pred:
        return
    try:
        feats = json.loads(ml_pred.get("features_json") or "{}")
    except (ValueError, TypeError):
        return
    with st.expander(t("trigger_algo.common.lime_expander",
                       "🍋 Explication locale LIME — Discover Weekly"), expanded=False):
        try:
            from lime.lime_tabular import LimeTabularExplainer

            from src.utils.ml_inference import FEATURE_COLUMNS, _resolve_path, load_model
            with open(_resolve_path("lime_background.json"), encoding="utf-8") as f:
                background = np.array(json.load(f), dtype=float)
            model = load_model("dw_classifier")
            x = np.array([float(feats.get(c, 0.0)) for c in FEATURE_COLUMNS])
            explainer = LimeTabularExplainer(
                background, feature_names=FEATURE_COLUMNS, mode="classification",
                class_names=["pas DW", "DW"], discretize_continuous=True, random_state=42)
            exp = explainer.explain_instance(
                x, lambda a: model.predict_proba(pd.DataFrame(a, columns=FEATURE_COLUMNS)),
                num_features=8)
            for cond, weight in exp.as_list():
                st.caption(f"{'🟢' if weight > 0 else '🔴'} {cond} · {weight:+.3f}")
            st.caption(t("trigger_algo.common.lime_caption",
                         "Contribution locale de chaque condition à la proba DW "
                         "(complément du SHAP waterfall — vue par perturbation)."))
        except ImportError:
            st.caption(t("trigger_algo.common.lime_not_installed",
                         "Module `lime` non installé — `pip install lime`."))
        except Exception as e:
            st.caption(t("trigger_algo.common.lime_unavailable",
                         "LIME indisponible : {err}").format(err=e))
