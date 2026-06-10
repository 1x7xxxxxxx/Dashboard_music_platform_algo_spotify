"""trigger_algo verdict — move-only split of _common."""
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
import json
import streamlit as st
from ._loaders import _clean_feat, _load_feature_importance, _load_scored_tracks


ELBOW_THRESHOLDS_28D = {"DW": 137, "RR": 130, "RADIO": 639}


HEURISTIC_GOALS = {"RR": 1000, "DW": 10000}


def _display_prob_bar(label: str, prob: float | None, forecast: int | None = None):
    if prob is None:
        st.write(t("trigger_algo.common.prob_insufficient", "**{label}** — données insuffisantes")
                 .format(label=label))
        return
    pct = min(max(prob, 0.0), 1.0)
    badge = "✅" if pct >= 0.6 else ("⚠️" if pct >= 0.3 else "❌")
    st.write(t("trigger_algo.common.prob_bar", "**{label}** {badge} — {pct:.0f}%")
             .format(label=label, badge=badge, pct=pct * 100))
    st.progress(pct)
    if forecast is not None and forecast > 0:
        ml_widgets.render_floor_forecast(
            t("trigger_algo.common.estimated_volume", "Volume estimé"), forecast)


def _show_ml_section(pred: dict):
    pred_date = pred.get("prediction_date", "—")
    model_v = pred.get("model_version", "v1")
    st.caption(t("trigger_algo.common.ml_pred_date", "Prédiction ML du **{date}** — modèle `{ver}`")
               .format(date=pred_date, ver=model_v))
    # RR volume regressor is unreliable (R²=0.32, notification-CTR noise) — gate the
    # forecast OUT and show the classification-only status caption instead.
    _rr_forecast = (pred.get("rr_streams_forecast_7d")
                    if ak.volume_forecast_reliable("RR") else None)
    _display_prob_bar("📡 Release Radar", pred.get("rr_probability"), _rr_forecast)
    _rr_note = ml_widgets.suppressed_note_text("RR")
    if _rr_note and pred.get("rr_probability") is not None:
        st.caption(f"📨 {_rr_note}")
    # DW volume is also suppressed in v3 (R²<0 group-CV) — gate the forecast OUT and
    # show the classification-only status, same pattern as RR.
    _dw_forecast = (pred.get("dw_streams_forecast_7d")
                    if ak.volume_forecast_reliable("DW") else None)
    _display_prob_bar("💎 Discover Weekly", pred.get("dw_probability"), _dw_forecast)
    ml_widgets.render_calibration_badge("DW", pred.get("dw_probability"))
    _dw_note = ml_widgets.suppressed_note_text("DW")
    if _dw_note and pred.get("dw_probability") is not None:
        st.caption(f"💎 {_dw_note}")
    # Calibration is now populated for RR + Radio too (v3) — surface it.
    ml_widgets.render_calibration_badge("RR", pred.get("rr_probability"))
    _display_prob_bar("📻 Radio Spotify", pred.get("radio_probability"),
                      pred.get("radio_streams_forecast_7d"))
    ml_widgets.render_calibration_badge("RADIO", pred.get("radio_probability"))


def _show_heuristic_section(current_total: float, current_pop: float):
    st.info(t("trigger_algo.common.heuristic_mode",
              "⚠️ **Mode Heuristique** — Aucune prédiction ML disponible. "
              "Lancez le DAG `ml_scoring_daily` pour obtenir des probabilités ML."))
    GOAL_RR = HEURISTIC_GOALS["RR"]
    GOAL_DW_S = HEURISTIC_GOALS["DW"]
    GOAL_DW_P = 30
    GOAL_RADIO = ELBOW_THRESHOLDS_28D["RADIO"]
    pct_rr = min(current_total / GOAL_RR, 1.0)
    pct_dw = (min(current_total / GOAL_DW_S, 1.0) + min(current_pop / GOAL_DW_P, 1.0)) / 2
    pct_radio = min(current_total / GOAL_RADIO, 1.0)
    st.write(t("trigger_algo.common.heur_rr", "**📡 Release Radar** ({pct}%)").format(pct=int(pct_rr * 100)))
    st.progress(pct_rr)
    if pct_rr >= 1.0:
        st.caption(t("trigger_algo.common.trigger_activated", "✅ Trigger théoriquement activé !"))
    else:
        st.caption(t("trigger_algo.common.rr_missing",
                     "Manque {n:,.0f} streams (seuil heuristique arrondi)")
                   .format(n=GOAL_RR - current_total))
    st.write(t("trigger_algo.common.heur_dw", "**💎 Discover Weekly** ({pct}%)").format(pct=int(pct_dw * 100)))
    st.progress(pct_dw)
    col1, col2 = st.columns(2)
    col1.info(t("trigger_algo.common.dw_streams_pct", "Streams : {pct:.0f}% (obj. 10k)")
              .format(pct=min(current_total / GOAL_DW_S, 1.0) * 100))
    col2.info(t("trigger_algo.common.dw_pop_pct", "Popularité : {pct:.0f}% (obj. 30)")
              .format(pct=min(current_pop / GOAL_DW_P, 1.0) * 100))
    st.write(t("trigger_algo.common.heur_radio", "**📻 Radio Spotify** ({pct}%)").format(pct=int(pct_radio * 100)))
    st.progress(pct_radio)
    if pct_radio >= 1.0:
        st.caption(t("trigger_algo.common.radio_detected",
                     "✅ Streams 28j au niveau d'un trigger Radio détecté."))
    else:
        st.caption(t("trigger_algo.common.radio_below",
                     "Streams 28j ({cur:,.0f}) sous le niveau de détection d'un "
                     "trigger Radio (~{goal:,.0f} algo-streams émis par la playlist).")
                   .format(cur=current_total, goal=GOAL_RADIO))
    st.caption(t(
        "trigger_algo.common.heuristic_thresholds",
        "ℹ️ Les cibles 1k/10k sont des **heuristiques arrondies**. Les seuils elbow "
        "(~{dw} DW · ~{rr} RR · ~{radio} Radio) sont le **minimum d'algo-streams qu'une "
        "playlist génère** au début d'un trigger — un signal de détection, **pas** un "
        "objectif de streams à produire soi-même pour déclencher."
    ).format(dw=ELBOW_THRESHOLDS_28D['DW'], rr=ELBOW_THRESHOLDS_28D['RR'],
             radio=ELBOW_THRESHOLDS_28D['RADIO']))


def _show_verdict_banner(ml_pred: dict | None) -> None:
    """Consolidated kill / optimize / scale decision at the top of the algos tab.

    Headline verdict on the best algorithmic opportunity (max of the 3 probs).
    Probabilities are NOT calibrated, so the 20/50% bands are decision heuristics,
    not exact likelihoods — the caveat is surfaced via ak.calibration_note().
    """
    if not ml_pred:
        return
    labels = {"DW": "Discover Weekly", "RR": "Release Radar", "RADIO": "Radio"}
    scored = {
        "DW": ml_pred.get("dw_probability"),
        "RR": ml_pred.get("rr_probability"),
        "RADIO": ml_pred.get("radio_probability"),
    }
    scored = {k: v for k, v in scored.items() if v is not None}
    if not scored:
        return
    best_algo = max(scored, key=scored.get)
    best_prob = scored[best_algo]

    try:
        feats = json.loads(ml_pred.get("features_json") or "{}")
    except (ValueError, TypeError):
        feats = {}

    if best_prob < 0.20:
        st.error(t(
            "trigger_algo.common.verdict_stop",
            "🔴 **STOP** — signaux algorithmiques faibles (meilleure piste : "
            "{algo} {prob:.0%}). Stoppez vos Meta Ads sur ce titre "
            "pour préserver votre budget."
        ).format(algo=labels[best_algo], prob=best_prob))
    elif best_prob < 0.50:
        st.warning(t(
            "trigger_algo.common.verdict_optimize",
            "🟠 **OPTIMISER** — potentiel détecté ({algo} {prob:.0%}), "
            "mais il manque un déclencheur."
        ).format(algo=labels[best_algo], prob=best_prob))
        actions = ak.build_coach_actions(best_algo, feats)
        if actions:
            a = actions[0]
            _lever = ml_widgets.lever_text(best_algo, a['feature'], a)
            _label = ml_widgets.label_text(a['feature'], a)
            st.caption(t("trigger_algo.common.verdict_lever1", "🎯 Levier #1 — {label} : {lever}")
                       .format(label=_label, lever=_lever))
    else:
        st.success(t(
            "trigger_algo.common.verdict_scale",
            "🟢 **SCALER** — ADN de hit détecté ({algo} {prob:.0%}). "
            "L'algorithme est prêt à prendre le relais : augmentez votre budget quotidien "
            "de ~20 % pour maximiser l'effet boule de neige."
        ).format(algo=labels[best_algo], prob=best_prob))
    note = ml_widgets.calibration_note_text(best_algo, best_prob)
    if note:
        st.caption(t("trigger_algo.common.verdict_reliability", "ℹ️ Fiabilité du score : {note}")
                   .format(note=note))
    st.caption(t(
        "trigger_algo.common.verdict_platt",
        "Probabilités calibrées (Platt) — les seuils 20 %/50 % correspondent à de vraies "
        "probabilités de déclenchement."
    ))


def _show_radio_snowball(db, artist_id) -> None:
    """Snowball radar — count catalogue songs the model rates as radio-active.

    Proxy via radio_probability >= 0.5 (NOT the imputed-to-0 feature
    HowManySongsDoYouHaveInRadioRightNow). 3+ active songs is the "trusted artist"
    signal: a new release is then more likely to get an algorithmic free pass.
    """
    df = _load_scored_tracks(db, artist_id)
    if df is None or "radio_probability" not in df:
        return
    n = int((df["radio_probability"].fillna(0) >= 0.5).sum())
    if n >= 3:
        st.success(t(
            "trigger_algo.common.snowball_safe",
            "🏆 **Statut « Valeur Sûre »** — {n} titres en radio algorithmique active. "
            "Moment idéal pour sortir un nouveau single : il sera poussé plus facilement."
        ).format(n=n))
    elif n >= 1:
        st.info(t(
            "trigger_algo.common.snowball_warming",
            "🔥 **En chauffe** — {n} titre(s) en radio active. Atteignez 3 titres pour "
            "débloquer le « passe-droit » algorithmique sur vos prochaines sorties."
        ).format(n=n))
    else:
        st.caption(t(
            "trigger_algo.common.snowball_cold",
            "❄️ Aucun titre en radio algorithmique active (estimation modèle). "
            "Concentrez les efforts pour percer un premier titre."
        ))
    st.caption(t(
        "trigger_algo.common.snowball_caption",
        "Effet boule de neige — estimation modèle (radio_probability ≥ 0,5), pas le "
        "décompte radio réel (donnée non collectée à l'inférence)."
    ))


def _show_resurrection_radar(db, artist_id) -> None:
    """Long-tail resurrection radar — old songs (>6 mo) with a sudden saves spike.

    Dormant until ~2 weeks of daily saves history accumulate (snapshot written by
    the ml_scoring_daily DAG → src/utils/saves_history.snapshot_saves).
    """
    try:
        from src.utils.saves_history import detect_saves_resurrection
        sparks = detect_saves_resurrection(db, artist_id)
    except Exception:
        return
    st.subheader(t("trigger_algo.common.resurrection_header", "✨ Résurrection longue traîne"))
    if not sparks:
        st.caption(t(
            "trigger_algo.common.resurrection_none",
            "Aucune étincelle détectée sur vos anciens titres (> 6 mois). Le radar "
            "s'active une fois ~2 semaines d'historique de saves accumulées "
            "(collecte quotidienne automatique)."
        ))
        return
    for s in sparks[:5]:
        st.success(t(
            "trigger_algo.common.resurrection_spark",
            "✨ **{song}** ({age} j) — +{gain} saves récents. "
            "Injectez un petit budget Ads aujourd'hui pour réveiller le Discover Weekly."
        ).format(song=s['song'], age=s['age_days'], gain=s['recent_gain']))


_PHASES = [
    (0, 35, "🚀 Phase 1 — Release Radar (0-35 j)",
     "Fenêtre de tir RR. Maximise les **clics/CTR** via Meta Ads sur une audience "
     "high-intent. **N'active PAS le Discovery Mode** (impact nul sur RR, −30 % de "
     "royalties pour rien). Objectif : convertir en followers + ≥ ~2 000 streams récents."),
    (35, 90, "🎧 Phase 2 — Discover Weekly (35-90 j)",
     "Le Release Radar s'arrête : c'est le moment de **réveiller le DW**, ne coupe pas "
     "le budget. Pivote vers l'**engagement qualitatif** — CTA explicite « Ajoutez ce "
     "titre en playlist » (vise ~175 ajouts + ~165 saves/28j), pas « écoutez »."),
    (90, 10_000, "📻 Phase 3 — Radio & longue traîne (90 j+)",
     "Stabilise la rentabilité. **Active le Discovery Mode** pour forcer l'entrée en "
     "Radio, puis applique le **kill-switch royalties** une fois le titre installé "
     "(> 10 000 streams/j en Radio) : l'inertie organique suffit, récupère tes 30 %."),
]


def _show_phase_strategy(ml_pred: dict | None) -> None:
    """Per-song strategic phase (1/2/3 by age) + the action that phase calls for."""
    if not ml_pred:
        return
    try:
        feats = json.loads(ml_pred.get("features_json") or "{}")
        days = float(feats.get("DaysSinceRelease"))
    except (ValueError, TypeError):
        return
    for lo, hi, title, advice in _PHASES:
        if lo <= days < hi:
            st.markdown(t("trigger_algo.common.phase_title", "**{title}** · titre à J+{days}")
                        .format(title=title, days=int(days)))
            st.caption(advice)
            break


def _show_feature_importance() -> None:
    """Ranked variable hierarchy per algorithm (gain XGBoost ≈ SHAP magnitude)."""
    imp = _load_feature_importance()
    if not imp:
        return
    with st.expander(t("trigger_algo.common.feat_imp_expander",
                       "📊 Hiérarchie des 13 variables par algorithme"), expanded=False):
        st.caption(t("trigger_algo.common.feat_imp_caption",
                     "Poids relatif de chaque variable dans la décision du modèle "
                     "(gain XGBoost — proxy de l'importance SHAP globale)."))
        cols = st.columns(3)
        algos = [("dw", "Discover Weekly"), ("rr", "Release Radar"), ("radio", "Radio")]
        for col, (algo, label) in zip(cols, algos):
            with col:
                st.markdown(f"**{label}**")
                rows = imp.get(algo, [])
                total = sum(r["gain"] for r in rows) or 1.0
                for i, r in enumerate(rows[:8], 1):
                    st.caption(f"{i}. {_clean_feat(r['feature'])} — {r['gain'] / total:.0%}")


def _show_discovery_mode_protocol() -> None:
    """Static Discovery Mode activation/kill-switch protocol (the 'pay-to-play' paradox)."""
    with st.expander(t("trigger_algo.common.dm_protocol_expander",
                       "🎚️ Protocole Discovery Mode (activation & kill-switch)"), expanded=False):
        st.markdown(t(
            "trigger_algo.common.dm_protocol_body",
            "- **Release Radar (semaine 1)** : impact **nul** — ne sacrifie pas 30 % de "
            "tes royalties, c'est inefficace.\n"
            "- **Radio (mois 3+)** : **levier d'activation** — il force l'entrée en Radio "
            "(le « videur VIP »), mais ne scale pas le volume.\n"
            "- **Kill-switch** : dès qu'un titre dépasse **~10 000 streams/jour en Radio**, "
            "**désactive** le Discovery Mode — l'inertie organique suffit, tu récupères "
            "ta marge de 30 %."
        ))
        st.caption(t(
            "trigger_algo.common.dm_protocol_caption",
            "Statut Discovery Mode live non collecté (imputé à 0 à l'inférence) — "
            "protocole affiché à titre indicatif."
        ))
