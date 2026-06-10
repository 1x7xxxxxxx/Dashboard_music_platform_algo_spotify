"""trigger_algo — shared helpers, loaders and constants (move-only split).

Extracted from the former monolithic trigger_algo.py; no behaviour change.
"""
from datetime import date
from plotly.subplots import make_subplots
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import show_empty_state
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
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


# Minimum algo-streams a playlist GENERATES at trigger onset over 28d (elbow of the
# training-data curve). It is the start-of-trigger detection floor — the least the
# playlist itself emits once it fires, NOT streams the artist must produce to trigger it.
ELBOW_THRESHOLDS_28D = {"DW": 137, "RR": 130, "RADIO": 639}


HEURISTIC_GOALS = {"RR": 1000, "DW": 10000}


_IMPUTED_FEATURES = {
    "HowManySongsDoYouHaveInRadioRightNow",
    "IsThisSongOptedIntoSpotifyDiscoveryMode",
    "NonAlgoStreams28Days_log",
}


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
    _rr_note = ak.volume_suppressed_note("RR")
    if _rr_note and pred.get("rr_probability") is not None:
        st.caption(f"📨 {_rr_note}")
    # DW volume is also suppressed in v3 (R²<0 group-CV) — gate the forecast OUT and
    # show the classification-only status, same pattern as RR.
    _dw_forecast = (pred.get("dw_streams_forecast_7d")
                    if ak.volume_forecast_reliable("DW") else None)
    _display_prob_bar("💎 Discover Weekly", pred.get("dw_probability"), _dw_forecast)
    ml_widgets.render_calibration_badge("DW", pred.get("dw_probability"))
    _dw_note = ak.volume_suppressed_note("DW")
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
    # Discovery Mode has a manual source: a KNOWN opt-out is real data, not imputed.
    dm_known = bool(feats.get("discovery_mode_known"))
    if dm_known:
        flagged.discard(_DM_KEY)
    if flagged:
        labels = [_FEATURE_LABELS.get(f, (f, True))[0] for f in sorted(flagged)]
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


def _load_ml_pred(db, track: str, artist_id) -> dict | None:
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          radio_streams_forecast_7d, pi_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE artist_id = %s AND song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (artist_id, track)
            )
        else:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          radio_streams_forecast_7d, pi_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (track,)
            )
        if rows:
            r = rows[0]
            return {
                "dw_probability": r[0], "rr_probability": r[1], "radio_probability": r[2],
                "dw_streams_forecast_7d": r[3], "rr_streams_forecast_7d": r[4],
                "radio_streams_forecast_7d": r[5], "pi_forecast_7d": r[6],
                "prediction_date": r[7], "model_version": r[8], "features_json": r[9],
            }
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600)
def _load_threshold_tables() -> dict | None:
    """PI-bracket trigger probabilities exported by machine_learning/train.py."""
    try:
        from src.utils.ml_inference import _resolve_path
        path = _resolve_path("threshold_tables.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


_PI_BINS = [(0, 10, "0-10"), (11, 20, "11-20"), (21, 30, "21-30"),
            (31, 40, "31-40"), (41, 50, "41-50"), (51, 10_000, "50+")]


def _pi_bracket(pi) -> str | None:
    if pi is None:
        return None
    for lo, hi, label in _PI_BINS:
        if lo <= pi <= hi:
            return label
    return None


def _show_pi_gate_section(ml_pred: dict | None) -> None:
    """B2 — 'you are HERE' on the PI→trigger curves, from the song's PI forecast."""
    st.subheader(t("trigger_algo.common.pi_gate_header", "🚪 Portes algorithmiques par Popularity Index"))
    st.caption(t(
        "trigger_algo.common.pi_gate_caption",
        "Le Popularity Index (0-100) est la porte d'entrée de chaque algorithme. "
        "La barre blanche situe votre titre ; n = taille d'échantillon par tranche."
    ))
    tables = _load_threshold_tables()
    if not tables:
        show_empty_state(t("trigger_algo.common.pi_tables_unavailable",
                           "Tables de seuils PI indisponibles — lancer `python3 machine_learning/train.py`."))
        return

    pi = ml_pred.get("pi_forecast_7d") if ml_pred else None
    here = _pi_bracket(pi)
    if pi is not None:
        st.metric(t("trigger_algo.common.pi_predicted_metric", "Popularity Index prédit"),
                  f"{int(pi)} / 100",
                  help=t("trigger_algo.common.pi_predicted_help",
                         "Régresseur PI (modèle v3). R²=0.92 [0.88–0.94] validé en "
                         "group-CV par chanson, MAE ~2 pts — robuste (vérifié 2026-06-05)."))
    else:
        st.info(t("trigger_algo.common.pi_no_pred",
                  "Pas de PI prédit pour ce titre (scoring ML quotidien non encore exécuté)."))

    brackets = tables.get("pi_brackets", [])
    algos = [("release_radar", "Release Radar (<35j)", "#4C78A8"),
             ("discover_weekly", "Discover Weekly", "#E45756"),
             ("radio", "Radio", "#54A24B")]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[a[1] for a in algos])
    for i, (key, _label, color) in enumerate(algos, start=1):
        data = tables.get(key, {})
        probs = [data.get(b, {}).get("prob") for b in brackets]
        ns = [data.get(b, {}).get("n", 0) for b in brackets]
        # Highlight the song's current bracket in white (visible on the dark
        # theme — the former #111111 was invisible on the near-black background).
        colors = ["#FFFFFF" if b == here else color for b in brackets]
        line_widths = [2 if b == here else 0 for b in brackets]
        fig.add_trace(go.Bar(
            x=brackets, y=probs, marker_color=colors,
            marker_line=dict(color="#1DB954", width=line_widths),
            text=[f"n={n}" for n in ns], textposition="outside",
            hovertemplate="PI %{x}<br>%{y:.0f}% déclenchement<br>%{text}<extra></extra>",
            showlegend=False,
        ), row=1, col=i)
        fig.update_yaxes(range=[0, 112], row=1, col=i)
    fig.update_layout(height=360, margin=dict(t=46, b=20))
    st.plotly_chart(fig, width='stretch')

    def _fmt(p):
        return f"{p:.0f}%" if p is not None else "n/a"

    if here:
        rr = tables.get("release_radar", {}).get(here, {}).get("prob")
        dw = tables.get("discover_weekly", {}).get(here, {}).get("prob")
        radio = tables.get("radio", {}).get(here, {}).get("prob")
        st.markdown(t(
            "trigger_algo.common.pi_chances",
            "À **PI {here}**, vos chances de déclenchement : "
            "Release Radar **{rr}** · Discover Weekly **{dw}** · Radio **{radio}**."
        ).format(here=here, rr=_fmt(rr), dw=_fmt(dw), radio=_fmt(radio)))
        # Reco engine — the highest-leverage DW gate (DW is the hardest door).
        dw_data = tables.get("discover_weekly", {})
        best = max(
            ((b, dw_data.get(b, {}).get("prob")) for b in brackets
             if dw_data.get(b, {}).get("prob") is not None),
            key=lambda t: t[1], default=(None, None),
        )
        if best[0] and best[0] != here:
            st.info(t(
                "trigger_algo.common.pi_lever1",
                "🎯 Levier #1 — le sésame Discover Weekly est à **PI {bracket}** "
                "({prob:.0f}% de déclenchement). Concentrez streams organiques + saves "
                "pour pousser le PI vers cette tranche avant de scaler le budget."
            ).format(bracket=best[0], prob=best[1]))
    st.caption(tables.get("note", ""))


def _show_pi_breakeven(ml_pred: dict | None) -> None:
    """PI-driven breakeven: the Popularity Index gates algorithmic revenue, so the
    real break-even question is whether the PI crosses each algo's trigger gate.
    """
    if not ml_pred:
        return
    pi = ml_pred.get("pi_forecast_7d")
    tables = _load_threshold_tables()
    if pi is None or not tables:
        return
    brackets = tables.get("pi_brackets", [])
    here = _pi_bracket(pi)
    st.markdown(t("trigger_algo.common.pi_breakeven_header",
                  "**🎯 Rentabilité pilotée par le Popularity Index**"))
    st.caption(t("trigger_algo.common.pi_breakeven_caption",
                 "PI prédit actuel : **{pi} / 100** (tranche {bracket}). Tu ne rentabilises "
                 "via un algo que si ton PI franchit sa porte de déclenchement.")
               .format(pi=int(pi), bracket=here))
    for key, label in (("discover_weekly", "Discover Weekly"),
                       ("radio", "Radio"), ("release_radar", "Release Radar")):
        data = tables.get(key, {})
        gate = next((b for b in brackets if (data.get(b, {}).get("prob") or 0) >= 50), None)
        if not gate:
            continue
        reached = here and brackets.index(here) >= brackets.index(gate)
        status = (t("trigger_algo.common.gate_reached", "✅ porte atteinte") if reached
                  else t("trigger_algo.common.gate_requires", "⛔ requiert PI {gate}").format(gate=gate))
        st.markdown(t("trigger_algo.common.gate_line", "- **{label}** : porte à PI **{gate}** — {status}")
                    .format(label=label, gate=gate, status=status))


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
            st.caption(t("trigger_algo.common.verdict_lever1", "🎯 Levier #1 — {label} : {lever}")
                       .format(label=a['label'], lever=a['lever']))
    else:
        st.success(t(
            "trigger_algo.common.verdict_scale",
            "🟢 **SCALER** — ADN de hit détecté ({algo} {prob:.0%}). "
            "L'algorithme est prêt à prendre le relais : augmentez votre budget quotidien "
            "de ~20 % pour maximiser l'effet boule de neige."
        ).format(algo=labels[best_algo], prob=best_prob))
    note = ak.calibration_note(best_algo, best_prob)
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


# Algo-streams an *established* trigger sustains over 28d (output the playlist emits once
# fully kicked in) — NOT a stream target the artist must hit to cause the trigger.
_TRIGGER_STREAM_TARGETS = {
    "Release Radar": 417,
    "Discover Weekly": 1333,
    "Radio": 8423,
}


_GATE_28D = {
    "Discover Weekly": {"streams": 9200, "listeners": 4100},
    "Release Radar": {"streams": 1300, "listeners": 600},
    "Radio": {"streams": 8400, "listeners": 4000},
}


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


@st.cache_data(ttl=3600)
def _load_feature_importance() -> dict | None:
    """Gain-based feature importance per algo, exported by machine_learning/train.py."""
    try:
        from src.utils.ml_inference import _resolve_path
        with open(_resolve_path("feature_importance.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _clean_feat(name: str) -> str:
    return (name.replace("_log", "").replace("_adj", "")
            .replace("Last28Days", " 28j").replace("Last7Days", " 7j"))


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


@st.cache_resource
def _load_xgb_model(model_key: str):
    """Load and cache an XGBoost Booster from mlruns. Returns None if unavailable."""
    try:
        import xgboost as xgb
        from src.utils.ml_inference import _resolve_path, MODEL_PATHS
        path = _resolve_path(MODEL_PATHS[model_key])
        model = xgb.Booster()
        model.load_model(path)
        return model
    except Exception:
        return None


def _compute_score_20(df: pd.DataFrame) -> pd.DataFrame:
    """Add score_20 column min-max scaled to /20 (best track = 20, worst = 0)."""
    dw = df["dw_probability"].fillna(0).astype(float)
    rr = df["rr_probability"].fillna(0).astype(float)
    radio = df["radio_probability"].fillna(0).astype(float)
    vel = df["velocity"].fillna(0).astype(float).clip(0, 5) / 5.0
    composite = 0.35 * dw + 0.35 * rr + 0.20 * radio + 0.10 * vel
    max_val = composite.max()
    min_val = composite.min()
    span = max_val - min_val
    df = df.copy()
    # Min-max stretch over the full 0-20 range. Degenerate catalogue (1 track or
    # all-equal composites) → span 0 → everyone gets 20.0 (no meaningful ranking).
    df["score_20"] = ((composite - min_val) / span * 20) if span > 0 else 20.0
    return df


def _load_scored_tracks(db, artist_id):
    """Latest-date scored tracks with score_20, sorted desc. None if empty.

    Shared by the Vue Globale benchmark table and the Budget top-N% selector.
    """
    cols = """song, dw_probability, rr_probability, radio_probability, streams_28d,
              CAST(features_json->>'Velocity_Streams' AS FLOAT) AS velocity"""
    try:
        if artist_id:
            df = db.fetch_df(
                f"""SELECT {cols} FROM ml_song_predictions
                    WHERE artist_id = %s AND prediction_date = (
                        SELECT MAX(prediction_date) FROM ml_song_predictions WHERE artist_id = %s
                    )""",
                (artist_id, artist_id),
            )
        else:
            df = db.fetch_df(
                f"""SELECT {cols} FROM ml_song_predictions
                    WHERE prediction_date = (SELECT MAX(prediction_date) FROM ml_song_predictions)"""
            )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return _compute_score_20(df).sort_values("score_20", ascending=False)


def _show_28d_gate(db, track: str, artist_id) -> None:
    """28-day streams/listeners gate per algo — is the track above each trigger threshold?

    Per-song listeners only exist as the 28-day snapshot (s4a_songs_global), not a daily
    series, so this is a gate panel rather than a chart line.
    """
    try:
        row = db.fetch_query(
            """SELECT listeners, streams FROM s4a_songs_global
               WHERE artist_id = %s AND song = %s AND time_window = '28d' LIMIT 1""",
            (artist_id, track),
        )
    except Exception:
        return
    if not row or row[0][0] is None:
        return
    listeners, streams = int(row[0][0] or 0), int(row[0][1] or 0)
    st.markdown(t("trigger_algo.common.gate28_header",
                  "**🚪 Porte 28 jours — streams & listeners vs seuils par algo**"))
    st.caption(t("trigger_algo.common.gate28_caption",
                 "Ce titre (28j) : **{streams:,} streams** · **{listeners:,} listeners**.")
               .format(streams=streams, listeners=listeners))
    cols = st.columns(len(_GATE_28D))
    for col, (algo, g) in zip(cols, _GATE_28D.items()):
        with col:
            st.markdown(f"**{algo}**")
            st.caption(t("trigger_algo.common.gate28_streams", "{mark} streams ≥ {thr:,}")
                       .format(mark='✅' if streams >= g['streams'] else '❌', thr=g['streams']))
            st.caption(t("trigger_algo.common.gate28_listeners", "{mark} listeners ≥ {thr:,}")
                       .format(mark='✅' if listeners >= g['listeners'] else '❌', thr=g['listeners']))
    st.caption(t("trigger_algo.common.gate28_note",
                 "Seuils 28j approximatifs, dérivés de data_anon.csv (knee du taux de succès)."))


def _show_budget_tier_selector(db, artist_id):
    """A&R portfolio tool: select the top-N% tracks by score (lift/precision tradeoff)."""
    st.subheader(t("trigger_algo.common.ar_selector_header", "🎯 Sélection A&R par budget (top-N%)"))
    df = _load_scored_tracks(db, artist_id)
    if df is None or len(df) < 3:
        st.info(t("trigger_algo.common.ar_selector_min",
                  "Outil disponible dès ≥ 3 titres scorés (échelle catalogue). "
                  "Lancez le DAG `ml_scoring_daily`."))
        return
    m = ak.ALGO_MODEL_METRICS.get("DW", {})
    n = len(df)
    pct = st.slider(t("trigger_algo.common.ar_slider", "Pousser le top N% par score"),
                    10, 100, 20, step=10,
                    help=t("trigger_algo.common.ar_slider_help",
                           "Seuil bas → précision haute (peu de gâchis) ; seuil haut → recall élevé."))
    k = max(1, (n * pct + 99) // 100)
    sel = df.head(k)
    c1, c2, c3 = st.columns(3)
    c1.metric(t("trigger_algo.common.ar_selected_metric", "Titres sélectionnés"), f"{k}/{n}")
    c2.metric(t("trigger_algo.common.ar_precision_metric", "Précision modèle"),
              f"{m.get('precision', 0) * 100:.0f}%")
    if pct <= 10:
        c3.metric(t("trigger_algo.common.ar_lift_metric", "Lift top-10%"),
                  f"×{m.get('lift_top10', 0):.1f}")
    else:
        c3.metric(t("trigger_algo.common.ar_recall_metric", "Recall (rappel)"),
                  f"{m.get('recall', 0) * 100:.0f}%")
    st.caption(t("trigger_algo.common.ar_caption",
                 "Budget serré → vise le top 10% (précision quasi parfaite, peu de gâchis). "
                 "Gros budget → baisse le seuil pour capter plus d'opportunités (recall ↑, précision ↓)."))
    show = sel[["song", "score_20"]].copy()
    show["score_20"] = show["score_20"].fillna(0).round(1)
    show.columns = [t("trigger_algo.common.ar_col_track", "Titre à pousser"),
                    t("trigger_algo.common.ar_col_score", "Score /20")]
    st.dataframe(show, hide_index=True, width="stretch")


def _show_velocity_budget_advice(db, track, artist_id, spent):
    """Concrete spend-smoothing advice when the track's velocity is too high.

    Cross-links the Explainabilité coach's qualitative 'smooth velocity' action to
    a euro amount: hyper-growth gets penalised, so suggest a ~30% spend cut to
    smooth the traffic. Thresholds come from algo_knowledge (no hardcoded cutoff).
    """
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT CAST(features_json->>'Velocity_Streams' AS FLOAT)
                   FROM ml_song_predictions WHERE song = %s AND artist_id = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (track, artist_id))
        else:
            rows = db.fetch_query(
                """SELECT CAST(features_json->>'Velocity_Streams' AS FLOAT)
                   FROM ml_song_predictions WHERE song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (track,))
        vel = float(rows[0][0]) if rows and rows[0][0] is not None else None
    except Exception:
        return
    # Gate + displayed cutoffs derive from algo_knowledge zones (single source of
    # truth) — the DW malus zone is the stricter/lower trigger.
    if vel is None or ak.zone_for_value("DW", "Velocity_Streams", vel) != "malus":
        return
    dw_thr = ak.velocity_penalty_threshold("DW")
    radio_thr = ak.velocity_penalty_threshold("RADIO")
    reduced = spent * 0.7
    st.warning(t(
        "trigger_algo.common.velocity_advice",
        "⚡ Vélocité élevée ({vel:.2f}) sur « {track} » — la Radio (seuil {radio:g}) "
        "et le DW ({dw:g}) pénalisent l'hyper-croissance (« feu de paille »). Suggestion : "
        "réduire la dépense de ~30 % ({spent:,.0f} € → {reduced:,.0f} €) pour lisser le trafic."
    ).format(vel=vel, track=track, radio=radio_thr, dw=dw_thr, spent=spent, reduced=reduced))


def _show_budget_pacing_calculator(db, artist_id) -> None:
    """Proactive budget-pacing planner: spread spend over the algo eval window to
    avoid the velocity-spike penalty. The euro->velocity mapping is heuristic (no
    model): the deliverable is the smoothing recommendation, not a guaranteed
    target velocity. Complements the reactive _show_velocity_budget_advice.
    """
    st.subheader(t("trigger_algo.common.pacing_header", "📅 Lisseur de budget (Pacing)"))
    default_budget, current_daily = 200.0, 0.0
    try:
        if artist_id:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget),0), COALESCE(SUM(daily_budget),0) "
                "FROM meta_campaigns WHERE artist_id = %s AND status = 'ACTIVE'", (artist_id,))
        else:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget),0), COALESCE(SUM(daily_budget),0) "
                "FROM meta_campaigns WHERE status = 'ACTIVE'")
        default_budget = float(row[0][0] or 0) or 200.0
        current_daily = float(row[0][1] or 0)
    except Exception:
        pass

    c1, c2 = st.columns(2)
    budget = c1.number_input(t("trigger_algo.common.pacing_budget_input", "Budget à étaler (€)"),
                             min_value=0.0, value=float(round(default_budget, 2)), step=10.0)
    window = c2.number_input(t("trigger_algo.common.pacing_window_input", "Fenêtre de lissage (jours)"),
                             min_value=7, max_value=90, value=28, step=1,
                             help=t("trigger_algo.common.pacing_window_help",
                                    "28 j = fenêtre d'évaluation des algos."))
    if budget <= 0:
        return
    per_day = budget / window
    st.metric(t("trigger_algo.common.pacing_daily_metric", "Dépense quotidienne recommandée"),
              f"{per_day:,.2f} €/jour")
    vthr = ak.velocity_penalty_threshold("DW")
    vtxt = f"~{vthr:g}" if vthr else t("trigger_algo.common.pacing_penalty_threshold", "le seuil de pénalité")
    st.info(t(
        "trigger_algo.common.pacing_info",
        "Étalez **{budget:,.0f} €** sur **{window} jours** (~{per_day:,.0f} €/jour) pour "
        "maintenir une croissance organique et éviter le « pic suspect » que le Discover "
        "Weekly pénalise (vélocité au-delà de {vtxt})."
    ).format(budget=budget, window=window, per_day=per_day, vtxt=vtxt))
    if current_daily > 0:
        burn_days = budget / current_daily
        if burn_days < 14:
            st.warning(t(
                "trigger_algo.common.pacing_burn_warning",
                "⚠️ Votre budget quotidien actuel (~{daily:,.0f} €/jour) épuiserait "
                "ce budget en ~{burn:.0f} jours → risque de pic de vélocité. "
                "Réduisez à ~{per_day:,.0f} €/jour."
            ).format(daily=current_daily, burn=burn_days, per_day=per_day))
    st.caption(t(
        "trigger_algo.common.pacing_caption",
        "Le lien €→vélocité est une heuristique de lissage (étalement sur la fenêtre "
        "d'éval), pas une vélocité-cible garantie."
    ))


_META_LEVER_QUERY = """
SELECT
    ctm.campaign_name,
    perf.spend, perf.results, perf.cpr, perf.ctr, perf.link_clicks,
    cta.ctas
FROM campaign_track_mapping ctm
LEFT JOIN (
    SELECT campaign_name, SUM(spend) AS spend, SUM(results) AS results,
           CASE WHEN SUM(results) > 0 THEN SUM(spend)::numeric / SUM(results) END AS cpr,
           AVG(NULLIF(ctr, 0)) AS ctr, SUM(link_clicks) AS link_clicks
    FROM meta_insights_performance WHERE artist_id = %s GROUP BY campaign_name
) perf ON LOWER(perf.campaign_name) = LOWER(ctm.campaign_name)
LEFT JOIN (
    SELECT mc.campaign_name, string_agg(DISTINCT a.call_to_action, ', ') AS ctas
    FROM meta_campaigns mc JOIN meta_ads a ON a.campaign_id = mc.campaign_id
    WHERE mc.artist_id = %s AND a.call_to_action IS NOT NULL
    GROUP BY mc.campaign_name
) cta ON LOWER(cta.campaign_name) = LOWER(ctm.campaign_name)
WHERE ctm.artist_id = %s AND LOWER(ctm.track_name) = LOWER(%s)
ORDER BY perf.cpr ASC NULLS LAST
"""


def _show_meta_lever_scoring(db, track: str, artist_id) -> None:
    """Score the marketing levers against REAL Meta Ads performance for this track.

    Joins the track's mapped campaigns (campaign_track_mapping) to their CSV perf
    (meta_insights_performance: CPR/CTR/results) + the ads' call_to_action — so the
    generic SHAP levers become "which campaign/CTA actually performed". Reuses the
    meta_cpr_optimizer join pattern.
    """
    st.markdown("---")
    st.markdown(t("trigger_algo.common.meta_lever_header",
                  "**🎯 Leviers marketing — performance Meta Ads réelle de ce titre**"))
    try:
        df = db.fetch_df(_META_LEVER_QUERY, (artist_id, artist_id, artist_id, track))
    except Exception as e:
        st.caption(t("trigger_algo.common.meta_lever_unavailable",
                     "Données Meta indisponibles : {err}").format(err=e))
        return
    if df is None or df.empty:
        st.caption(t("trigger_algo.common.meta_lever_no_campaign",
                     "Aucune campagne Meta mappée à ce titre — mappe-les dans la vue "
                     "« Meta ↔ Spotify » pour scorer tes leviers sur les perfs réelles."))
        return

    df = df.copy()
    df["cpr"] = pd.to_numeric(df["cpr"], errors="coerce")
    df["ctr"] = pd.to_numeric(df["ctr"], errors="coerce")
    show = df.rename(columns={
        "campaign_name": t("trigger_algo.common.meta_col_campaign", "Campagne"),
        "spend": "Spend €", "results": "Results",
        "cpr": "CPR €", "ctr": "CTR %",
        "link_clicks": t("trigger_algo.common.meta_col_clicks", "Clics"), "ctas": "CTA",
    })
    st.dataframe(show, hide_index=True, width='stretch')

    scored = df.dropna(subset=["cpr"])
    if not scored.empty:
        best = scored.loc[scored["cpr"].idxmin()]
        worst = scored.loc[scored["cpr"].idxmax()]
        st.success(t("trigger_algo.common.meta_best_lever",
                     "✅ Meilleur levier : **{name}** — CPR {cpr:.3f} € ({cta})")
                   .format(name=best['campaign_name'], cpr=best['cpr'],
                           cta=best['ctas'] or t("trigger_algo.common.cta_na", "CTA n/d")))
        if worst["campaign_name"] != best["campaign_name"]:
            st.warning(t("trigger_algo.common.meta_worst_lever",
                         "⚠️ Moins efficace : **{name}** — CPR {cpr:.3f} € "
                         "→ réalloue vers le CTA/audience qui performe.")
                       .format(name=worst['campaign_name'], cpr=worst['cpr']))
    st.caption(t("trigger_algo.common.meta_cpr_caption",
                 "CPR = coût par résultat (plus bas = mieux). Croise avec le levier SHAP "
                 "pénalisé : le CTA « Ajouter en playlist » bat « Écouter » sur le DW."))


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


_LIFECYCLE_AGE_BINS = [
    ("0-5", 1, 0, 5), ("5-10", 2, 5, 10), ("10-25", 3, 10, 25),
    ("25-50", 4, 25, 50), ("50-100", 5, 50, 100), ("100+", 6, 100, 10**9),
]


_LIFECYCLE_PALETTE = {"DW": "rgb(0,200,220)", "RR": "rgb(255,165,0)", "RADIO": "rgb(29,185,84)"}


_LIFECYCLE_LABELS = {"DW": "💎 Discover Weekly", "RR": "📡 Release Radar", "RADIO": "📻 Radio"}


@st.cache_data(ttl=3600)
def _load_lifecycle_benchmark(_db, dataset_version="v2"):
    """Load the GLOBAL cohort lifecycle curves. `_db` underscored → not hashed.

    Prefers v2 (conditioned-on-trigger seed, migration 041 — meaningful medians +
    populated total_stream_median). Falls back to v1 when v2 is absent (migration not yet
    applied) so the tab never regresses to "benchmark indisponible".
    """
    def _fetch(version):
        return _db.fetch_df(
            """SELECT algorithm, age_week_bin, age_week_bin_order,
                      ratio_q1, ratio_median, ratio_q3,
                      total_stream_median, sample_count
               FROM algo_lifecycle_benchmark
               WHERE dataset_version = %s
               ORDER BY age_week_bin_order""",
            (version,),
        )
    try:
        df = _fetch(dataset_version)
        if (df is None or df.empty) and dataset_version != "v1":
            return _fetch("v1")
        return df
    except Exception:
        return None


def _compute_age_weeks(release_date):
    if release_date is None:
        return None
    return max(0, (date.today() - release_date).days // 7)


def _age_week_order(age_weeks):
    """Map an age-in-weeks to its benchmark bin (order, label)."""
    if age_weeks is None:
        return None, None
    for label, order, lo, hi in _LIFECYCLE_AGE_BINS:
        if lo <= age_weeks < hi:
            return order, label
    return None, None


def _lifecycle_band_fig(curve_df, algo_label, live_order, color):
    x = list(curve_df["age_week_bin_order"])
    rgba = color.replace("rgb(", "rgba(").replace(")", ", 0.18)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=curve_df["ratio_q3"], mode="lines",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=curve_df["ratio_q1"], mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor=rgba,
                             name=t("trigger_algo.common.band_p25_p75", "P25–P75 (cohorte)")))
    fig.add_trace(go.Scatter(x=x, y=curve_df["ratio_median"], mode="lines+markers",
                             line=dict(color=color, width=3),
                             name=t("trigger_algo.common.band_median", "Médiane cohorte")))
    fig.add_hline(y=1.0, line_dash="dot", line_color="grey",
                  annotation_text=t("trigger_algo.common.band_category_avg", "Moyenne catégorie (1.0×)"))
    if live_order is not None:
        fig.add_vline(x=live_order, line_dash="dash", line_color="#ffffff",
                      annotation_text=t("trigger_algo.common.band_this_track", "Ce titre"),
                      annotation_position="top")
    fig.update_layout(title=t("trigger_algo.common.band_chart_title",
                              "{algo} — ratio de standardisation par âge").format(algo=algo_label),
                      height=300,
                      xaxis_title=t("trigger_algo.common.band_axis_age", "Âge du titre (semaines)"),
                      yaxis_title=t("trigger_algo.common.band_axis_ratio",
                                    "Ratio (titre / moyenne catégorie)"),
                      hovermode="x unified", legend=dict(orientation="h", y=1.18),
                      margin=dict(t=70))
    fig.update_xaxes(tickmode="array", tickvals=x, ticktext=list(curve_df["age_week_bin"]))
    return fig


def _standardization_block(db, track, artist_id, age_weeks, benchmark_df):
    st.markdown(t("trigger_algo.common.std_position_header", "#### 📍 Position de ce titre vs cohorte"))
    if age_weeks is None:
        st.info(t("trigger_algo.common.std_unknown_release",
                  "Date de sortie inconnue — impossible de situer le titre."))
        return
    order, bin_label = _age_week_order(age_weeks)
    ref = benchmark_df[benchmark_df["age_week_bin_order"] == order]["total_stream_median"].dropna()
    if ref.empty:
        st.info(t(
            "trigger_algo.common.std_no_cohort_ref",
            "Âge : **{age} sem.** (tranche {bin}). Référence cohorte "
            "total-streams indisponible (artefact provisoire) — seul l'âge est "
            "superposé sur les courbes ci-dessus."
        ).format(age=age_weeks, bin=bin_label))
        return
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline
                   WHERE song = %s AND artist_id = %s
                     AND song NOT ILIKE %s AND date >= CURRENT_DATE - 28""",
                (track, artist_id, "%1x7xxxxxxx%"))
        else:
            rows = db.fetch_query(
                """SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline
                   WHERE song = %s AND song NOT ILIKE %s AND date >= CURRENT_DATE - 28""",
                (track, "%1x7xxxxxxx%"))
        live_28d = float(rows[0][0]) if rows else 0.0
    except Exception:
        st.info(t("trigger_algo.common.std_no_streams", "Streams du titre indisponibles."))
        return
    cohort_med = float(ref.iloc[0])
    ratio = live_28d / cohort_med if cohort_med > 0 else 0.0
    st.metric(t("trigger_algo.common.std_position_metric", "Position vs cohorte (tranche {bin})")
              .format(bin=bin_label), f"{ratio:.2f}×",
              delta=t("trigger_algo.common.std_vs_median", "{pct:+.0f}% vs médiane")
              .format(pct=(ratio - 1) * 100))
    st.caption(t(
        "trigger_algo.common.std_ratio_caption",
        "Ratio basé sur le **total** des streams (toutes sources, 28j). La "
        "répartition par algorithme provient de la cohorte globale et n'est PAS "
        "mesurée sur ce titre."
    ))


def _lifecycle_legend():
    with st.expander(t("trigger_algo.common.legend_expander",
                       "ℹ️ Comprendre les courbes de vie & la standardisation"), expanded=False):
        st.markdown(t(
            "trigger_algo.common.legend_body",
            "**Ratio de standardisation** : compare les streams de ce titre à la moyenne "
            "des titres de la même *catégorie de poids* (décile de followers pour DW/RR, "
            "bucket de popularité pour Radio). **1.0× = dans la moyenne**, >1.0× = "
            "au-dessus, <1.0× = en dessous. Le ratio porte sur le **total** des streams ; "
            "la ventilation par algorithme vient de la cohorte globale.\n\n"
            "**Phases du cycle de vie :**\n"
            "- 🕳️ **Vallée de la mort** (Radio, sem. 5-10) : creux algorithmique après l'élan initial.\n"
            "- 📈 **Résurrection** (Radio, sem. 25-100+) : reprise long-tail si l'engagement tient.\n"
            "- 🧗 **Falaise** (Release Radar, après sem. 5-6) : RR cible la nouveauté, l'exposition chute vite.\n"
            "- ♾️ **Pas d'expiration** (Discover Weekly) : DW peut ré-exposer un titre durablement.\n\n"
            "Courbes = bande P25-P75 + médiane d'une cohorte **globale** (statique). "
            "Ligne verticale blanche = âge actuel de votre titre."
        ))
