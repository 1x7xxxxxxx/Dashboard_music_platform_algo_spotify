"""Vue Road to Algorithms — scoring ML, suivi, budget, SHAP, ROI.

Type: Feature
Uses: ml_song_predictions, s4a_song_timeline, s4a_audience, s4a_songs_global,
      meta_campaigns, meta_insights_performance_day, imusician_monthly_revenue,
      track_popularity_history, algo_lifecycle_benchmark
Depends on: view_session, ui.show_empty_state, kpi_helpers.get_monthly_roi_series,
            ml_inference.FEATURE_COLUMNS / MODEL_PATHS / _resolve_path
"""
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta

from src.dashboard.utils import view_session, ml_widgets
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils.ui import show_empty_state


# ── Feature labels & marketing actions ──────────────────────────────────────
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


# ── Algorithm thresholds (single source of truth) ────────────────────────────
# Elbow thresholds learned from the training-set distribution on 28-day streams.
# These are the exact cut-offs the XGBoost classifiers were trained against
# (machine_learning/data_analysis_ml_perso.ipynb : y = <algo>StreamsLast28Days > t).
ELBOW_THRESHOLDS_28D = {"DW": 137, "RR": 130, "RADIO": 639}
# Legacy round-number stream goals used by the pre-ML heuristic display. Kept for
# continuity but labelled explicitly as heuristic — they are NOT the elbow values.
HEURISTIC_GOALS = {"RR": 1000, "DW": 10000}

# Model inputs still imputed to 0 at inference (no source yet — Phase 2 / S4A API).
# Saves, PlaylistAdds, ReleaseConsistency and the listeners/streams ratio are now
# computed live (see ml_inference.build_features). Surfaced in the Explainabilité
# tab so probabilities are read as indicative.
_IMPUTED_FEATURES = {
    "HowManySongsDoYouHaveInRadioRightNow",
    "IsThisSongOptedIntoSpotifyDiscoveryMode",
    "NonAlgoStreams28Days_log",
}


# ── Existing helpers (unchanged) ─────────────────────────────────────────────
def _display_prob_bar(label: str, prob: float | None, forecast: int | None = None):
    if prob is None:
        st.write(f"**{label}** — données insuffisantes")
        return
    pct = min(max(prob, 0.0), 1.0)
    badge = "✅" if pct >= 0.6 else ("⚠️" if pct >= 0.3 else "❌")
    st.write(f"**{label}** {badge} — {pct * 100:.0f}%")
    st.progress(pct)
    if forecast is not None and forecast > 0:
        ml_widgets.render_floor_forecast("Volume estimé", forecast)


def _show_ml_section(pred: dict):
    pred_date = pred.get("prediction_date", "—")
    model_v = pred.get("model_version", "v1")
    st.caption(f"Prédiction ML du **{pred_date}** — modèle `{model_v}`")
    # RR volume regressor is unreliable (R²=0.32, notification-CTR noise) — gate the
    # forecast OUT and show the classification-only status caption instead.
    _rr_forecast = (pred.get("rr_streams_forecast_7d")
                    if ak.volume_forecast_reliable("RR") else None)
    _display_prob_bar("📡 Release Radar", pred.get("rr_probability"), _rr_forecast)
    _rr_note = ak.volume_suppressed_note("RR")
    if _rr_note and pred.get("rr_probability") is not None:
        st.caption(f"📨 {_rr_note}")
    _display_prob_bar("💎 Discover Weekly", pred.get("dw_probability"), pred.get("dw_streams_forecast_7d"))
    ml_widgets.render_calibration_badge("DW", pred.get("dw_probability"))
    _display_prob_bar("📻 Radio Spotify", pred.get("radio_probability"),
                      pred.get("radio_streams_forecast_7d"))


def _show_heuristic_section(current_total: float, current_pop: float):
    st.info("⚠️ **Mode Heuristique** — Aucune prédiction ML disponible. "
            "Lancez le DAG `ml_scoring_daily` pour obtenir des probabilités ML.")
    GOAL_RR = HEURISTIC_GOALS["RR"]
    GOAL_DW_S = HEURISTIC_GOALS["DW"]
    GOAL_DW_P = 30
    GOAL_RADIO = ELBOW_THRESHOLDS_28D["RADIO"]
    pct_rr = min(current_total / GOAL_RR, 1.0)
    pct_dw = (min(current_total / GOAL_DW_S, 1.0) + min(current_pop / GOAL_DW_P, 1.0)) / 2
    pct_radio = min(current_total / GOAL_RADIO, 1.0)
    st.write(f"**📡 Release Radar** ({int(pct_rr * 100)}%)")
    st.progress(pct_rr)
    if pct_rr >= 1.0:
        st.caption("✅ Trigger théoriquement activé !")
    else:
        st.caption(f"Manque {GOAL_RR - current_total:,.0f} streams (seuil heuristique arrondi)")
    st.write(f"**💎 Discover Weekly** ({int(pct_dw * 100)}%)")
    st.progress(pct_dw)
    col1, col2 = st.columns(2)
    col1.info(f"Streams : {min(current_total / GOAL_DW_S, 1.0) * 100:.0f}% (obj. 10k)")
    col2.info(f"Popularité : {min(current_pop / GOAL_DW_P, 1.0) * 100:.0f}% (obj. 30)")
    st.write(f"**📻 Radio Spotify** ({int(pct_radio * 100)}%)")
    st.progress(pct_radio)
    if pct_radio >= 1.0:
        st.caption("✅ Seuil Radio (elbow) atteint !")
    else:
        st.caption(f"Manque {GOAL_RADIO - current_total:,.0f} streams (seuil elbow 28j)")
    st.caption(
        "ℹ️ Les cibles 1k/10k sont des **heuristiques arrondies**. Les vrais seuils "
        f"d'entraînement (elbow, 28j) sont ~{ELBOW_THRESHOLDS_28D['DW']} (DW), "
        f"~{ELBOW_THRESHOLDS_28D['RR']} (RR), ~{ELBOW_THRESHOLDS_28D['RADIO']} (Radio) streams."
    )


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
    st.subheader("🔍 Facteurs clés & leviers marketing")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**✅ Points forts**")
        for item in positives[:3]:
            st.success(f"**{item['label']}** : {item['display']}")
        if not positives:
            st.caption("Aucun facteur positif détecté.")
    with col2:
        st.write("**⚠️ Points à améliorer — actions recommandées**")
        for item in negatives[:3]:
            st.warning(f"**{item['label']}** : {item['display']}")
            action = _MARKETING_ACTIONS.get(item["key"])
            if action:
                st.caption(f"→ {action}")
        if not negatives:
            st.caption("Aucun facteur négatif détecté.")


def _show_imputation_caveat(feats: dict, feature_columns) -> None:
    """Warn which model inputs are imputed/absent → probabilities are indicative."""
    missing = [f for f in feature_columns if f not in feats]
    zeroed = [f for f in feature_columns
              if f in feats and f in _IMPUTED_FEATURES and float(feats.get(f, 0.0)) == 0.0]
    flagged = sorted(set(missing) | set(zeroed))
    if not flagged:
        return
    labels = [_FEATURE_LABELS.get(f, (f, True))[0] for f in flagged]
    st.warning(
        f"⚠️ **{len(flagged)}/{len(feature_columns)} variables imputées à 0/neutre** "
        "faute de données S4A : les probabilités sont **indicatives, non calibrées** "
        "(comparaison relative entre titres, pas une probabilité absolue).\n\n"
        "Variables concernées : " + ", ".join(labels) + "."
    )


# ── Data helpers ─────────────────────────────────────────────────────────────
def _load_ml_pred(db, track: str, artist_id) -> dict | None:
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          radio_streams_forecast_7d,
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
                          radio_streams_forecast_7d,
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
                "radio_streams_forecast_7d": r[5],
                "prediction_date": r[6], "model_version": r[7], "features_json": r[8],
            }
    except Exception:
        pass
    return None


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
    """Add score_20 column normalised to /20 across all rows."""
    dw = df["dw_probability"].fillna(0).astype(float)
    rr = df["rr_probability"].fillna(0).astype(float)
    radio = df["radio_probability"].fillna(0).astype(float)
    vel = df["velocity"].fillna(0).astype(float).clip(0, 5) / 5.0
    composite = 0.35 * dw + 0.35 * rr + 0.20 * radio + 0.10 * vel
    max_val = composite.max()
    df = df.copy()
    df["score_20"] = (composite / max_val * 20) if max_val > 0 else 0.0
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


# ── Tab 1 — Vue Globale ───────────────────────────────────────────────────────
def _show_tab_global(db, track: str, artist_id, date_from, date_to, ml_pred, release_date=None):
    st.subheader("📊 Métriques sur la période sélectionnée")

    # Select the appropriate s4a_songs_global snapshot window based on period length.
    # ≤35 days → 28d snapshot; anything longer → 12m snapshot.
    _period_days = (date_to - date_from).days
    _tw = '28d' if _period_days <= 35 else '12m'

    # Listeners — per-track snapshot from s4a_songs_global
    try:
        _lrow = db.fetch_query(
            "SELECT listeners FROM s4a_songs_global "
            "WHERE artist_id = %s AND song = %s AND time_window = %s "
            "ORDER BY collected_at DESC LIMIT 1",
            (artist_id, track, _tw),
        ) if artist_id else db.fetch_query(
            "SELECT listeners FROM s4a_songs_global "
            "WHERE song = %s AND time_window = %s "
            "ORDER BY collected_at DESC LIMIT 1",
            (track, _tw),
        )
        listeners = int(_lrow[0][0]) if _lrow and _lrow[0][0] is not None else None
    except Exception:
        listeners = None

    # Streams — per-track cumulative over period from s4a_song_timeline
    try:
        if artist_id:
            streams = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline WHERE song = %s AND artist_id = %s AND date BETWEEN %s AND %s",
                (track, artist_id, date_from, date_to)
            )[0][0]
        else:
            streams = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline WHERE song = %s AND date BETWEEN %s AND %s",
                (track, date_from, date_to)
            )[0][0]
    except Exception:
        streams = None

    # Saves — per-track snapshot from s4a_songs_global
    try:
        _srow = db.fetch_query(
            "SELECT saves FROM s4a_songs_global "
            "WHERE artist_id = %s AND song = %s AND time_window = %s "
            "ORDER BY collected_at DESC LIMIT 1",
            (artist_id, track, _tw),
        ) if artist_id else db.fetch_query(
            "SELECT saves FROM s4a_songs_global "
            "WHERE song = %s AND time_window = %s "
            "ORDER BY collected_at DESC LIMIT 1",
            (track, _tw),
        )
        saves = int(_srow[0][0]) if _srow and _srow[0][0] is not None else None
    except Exception:
        saves = None

    # Playlist adds — most recent snapshot in the selected period (sémantique post-migration 024:
    # 'count' est cumulatif par snapshot daté via recorded_at, pas incrémental par fenêtre)
    try:
        _parow = db.fetch_query(
            "SELECT count FROM s4a_song_playlist_adds "
            "WHERE artist_id = %s AND song = %s AND recorded_at BETWEEN %s AND %s "
            "ORDER BY recorded_at DESC LIMIT 1",
            (artist_id, track, date_from, date_to),
        ) if artist_id else None
        playlist_adds = int(_parow[0][0]) if _parow and _parow[0][0] is not None else 0
    except Exception:
        playlist_adds = 0

    _tw_label = "28j" if _tw == '28d' else "12m"
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Listeners ({_tw_label})", f"{int(listeners or 0):,}" if listeners is not None else "—",
                help=f"Snapshot {_tw_label} depuis s4a_songs_global (source : S4A export)")
    col2.metric(f"Streams titre ({_tw_label})", f"{int(streams or 0):,}" if streams is not None else "—")
    col3.metric(f"Saves ({_tw_label})", f"{int(saves or 0):,}" if saves is not None else "—",
                help=f"Snapshot {_tw_label} depuis s4a_songs_global")
    col4.metric("Playlist adds (période)", f"{int(playlist_adds):,}",
                help="Saisie manuelle via la section Ajouts en playlist ci-dessous")

    st.markdown("---")

    # ── Ajouts en playlist (saisie manuelle) ─────────────────────────────────
    st.subheader("🎧 Ajouts en playlist")
    try:
        # Most recent snapshot regardless of selected period
        pl_row = db.fetch_query(
            "SELECT count, recorded_at FROM s4a_song_playlist_adds "
            "WHERE artist_id = %s AND song = %s "
            "ORDER BY recorded_at DESC LIMIT 1",
            (artist_id, track),
        ) if artist_id else db.fetch_query(
            "SELECT count, recorded_at FROM s4a_song_playlist_adds "
            "WHERE song = %s ORDER BY recorded_at DESC LIMIT 1",
            (track,),
        )
        current_pl_count = int(pl_row[0][0]) if pl_row and pl_row[0][0] is not None else 0
        last_recorded = pl_row[0][1] if pl_row else None
    except Exception:
        current_pl_count = 0
        last_recorded = None

    st.metric(
        "Playlists ajoutées",
        current_pl_count,
        help=f"Dernier enregistrement : {last_recorded or '—'}. "
             "Donnée visible dans l'UI Spotify for Artists uniquement — à saisir manuellement.",
    )

    with st.expander("✏️ Mettre à jour", expanded=False):
        st.caption("Saisissez le nombre de playlists affiché dans S4A pour cette track.")
        with st.form(key=f"pl_count_form_{track}_{artist_id}", clear_on_submit=False):
            fc1, fc2 = st.columns([2, 1])
            new_count = fc1.number_input(
                "Nombre de playlists",
                min_value=0,
                value=current_pl_count,
                step=1,
            )
            entry_date = fc2.date_input(
                "Date de relevé",
                value=date_to,
                format="YYYY-MM-DD",
            )
            if st.form_submit_button("Enregistrer", type="primary"):
                try:
                    db.upsert_many(
                        table='s4a_song_playlist_adds',
                        data=[{
                            'artist_id':   artist_id,
                            'song':        track,
                            'recorded_at': entry_date,
                            'count':       int(new_count),
                        }],
                        conflict_columns=['artist_id', 'song', 'recorded_at'],
                        update_columns=['count', 'collected_at'],
                    )
                    st.success(f"{int(new_count)} playlist(s) enregistrée(s) au {entry_date}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

    st.markdown("---")

    # Score /20 benchmark
    st.subheader("🏆 Score /20 — Benchmark toutes les tracks")
    try:
        df_bench = _load_scored_tracks(db, artist_id)

        if df_bench is not None and not df_bench.empty:
            display = df_bench[["song", "score_20", "dw_probability", "rr_probability",
                                "radio_probability", "streams_28d"]].copy()
            display["score_20"] = display["score_20"].fillna(0).round(1)
            display["dw_probability"] = (display["dw_probability"].fillna(0) * 100).round(0).astype(int)
            display["rr_probability"] = (display["rr_probability"].fillna(0) * 100).round(0).astype(int)
            display["radio_probability"] = (display["radio_probability"].fillna(0) * 100).round(0).astype(int)
            display["streams_28d"] = display["streams_28d"].fillna(0).astype(int)
            display.columns = ["Titre", "Score /20", "DW %", "RR %", "Radio %", "Streams 28j"]

            def _color_score(val):
                if val >= 14:
                    return "background-color: #1a4731; color: #1DB954"
                elif val >= 8:
                    return "background-color: #3d2a00; color: #FFA500"
                return "background-color: #3d1010; color: #FF6B6B"

            def _highlight_selected(row):
                if row["Titre"] == track:
                    return ["font-weight: bold; border-left: 3px solid #1DB954"] * len(row)
                return [""] * len(row)

            styled = (
                display.style
                .format(na_rep="—")
                .applymap(_color_score, subset=["Score /20"])
                .apply(_highlight_selected, axis=1)
            )
            st.dataframe(styled, hide_index=True, width='stretch')
        else:
            st.info("Aucune prédiction ML disponible pour le benchmark.")
    except Exception as e:
        st.warning(f"Score benchmark indisponible : {e}")

    st.markdown("---")

    # J+28 quick stats + probability bars
    st.subheader("🎯 Objectifs Algorithmiques (J+28)")
    try:
        if artist_id:
            df_full = db.fetch_df(
                "SELECT date, streams FROM s4a_song_timeline WHERE song = %s AND artist_id = %s ORDER BY date ASC",
                (track, artist_id)
            )
        else:
            df_full = db.fetch_df(
                "SELECT date, streams FROM s4a_song_timeline WHERE song = %s ORDER BY date ASC",
                (track,)
            )
        if not df_full.empty:
            df_full["date"] = pd.to_datetime(df_full["date"])
            # Use actual release_date from tracks table; fall back to timeline min only if unavailable
            rd = pd.Timestamp(release_date) if release_date else df_full["date"].min()
            end_28 = rd + timedelta(days=28)
            df_28 = df_full[(df_full["date"] >= rd) & (df_full["date"] <= end_28)].copy()
            df_28["day_index"] = (df_28["date"] - rd).dt.days
            df_28["streams_cumul"] = df_28["streams"].cumsum()
            current_total = float(df_28["streams_cumul"].max()) if not df_28.empty else 0
            days_elapsed = int(df_28["day_index"].max()) if not df_28.empty else 0
            c1, c2 = st.columns(2)
            c1.metric("Jours écoulés (J+28)", f"{days_elapsed}/28",
                      delta=f"{max(0, 28 - days_elapsed)} restants", delta_color="inverse")
            c2.metric("Streams cumulés J+28", f"{current_total:,.0f}")
        else:
            current_total, days_elapsed = 0, 0
    except Exception:
        current_total, days_elapsed = 0, 0

    if ml_pred:
        _show_ml_section(ml_pred)
    else:
        _show_heuristic_section(current_total, 0)


# ── Tab 2 — Suivi Algorithmes ─────────────────────────────────────────────────
def _show_tab_algos(db, track: str, artist_id, date_from, date_to, ml_pred, release_date=None):
    st.subheader("📈 Streams & probabilités algorithmiques")
    try:
        if artist_id:
            df_streams = db.fetch_df(
                "SELECT date, streams FROM s4a_song_timeline WHERE song = %s AND artist_id = %s AND date BETWEEN %s AND %s ORDER BY date",
                (track, artist_id, date_from, date_to)
            )
            df_proba = db.fetch_df(
                """SELECT prediction_date, dw_probability, rr_probability, radio_probability
                   FROM ml_song_predictions
                   WHERE song = %s AND artist_id = %s AND prediction_date BETWEEN %s AND %s
                   ORDER BY prediction_date""",
                (track, artist_id, date_from, date_to)
            )
        else:
            df_streams = db.fetch_df(
                "SELECT date, streams FROM s4a_song_timeline WHERE song = %s AND date BETWEEN %s AND %s ORDER BY date",
                (track, date_from, date_to)
            )
            df_proba = db.fetch_df(
                """SELECT prediction_date, dw_probability, rr_probability, radio_probability
                   FROM ml_song_predictions
                   WHERE song = %s AND prediction_date BETWEEN %s AND %s
                   ORDER BY prediction_date""",
                (track, date_from, date_to)
            )

        if df_streams.empty:
            st.info("Aucun stream sur cette période.")
        else:
            df_streams["date"] = pd.to_datetime(df_streams["date"])
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(
                x=df_streams["date"], y=df_streams["streams"],
                name="Streams", marker_color="#1DB954", opacity=0.8
            ), secondary_y=False)

            if not df_proba.empty:
                df_proba["prediction_date"] = pd.to_datetime(df_proba["prediction_date"])
                fig.add_trace(go.Scatter(
                    x=df_proba["prediction_date"], y=df_proba["dw_probability"] * 100,
                    name="Discover Weekly %", mode="lines+markers",
                    line=dict(color="#FF6B6B", width=2)
                ), secondary_y=True)
                fig.add_trace(go.Scatter(
                    x=df_proba["prediction_date"], y=df_proba["rr_probability"] * 100,
                    name="Release Radar %", mode="lines+markers",
                    line=dict(color="#4ECDC4", width=2)
                ), secondary_y=True)
                fig.add_trace(go.Scatter(
                    x=df_proba["prediction_date"], y=df_proba["radio_probability"] * 100,
                    name="Radio %", mode="lines+markers",
                    line=dict(color="#FFE66D", width=2)
                ), secondary_y=True)
            else:
                st.caption("Aucun historique de probabilités ML sur cette période.")

            fig.update_layout(
                title=f"Streams & probabilités — {track}",
                hovermode="x unified", height=480,
                legend=dict(orientation="h", y=1.12)
            )
            fig.update_yaxes(title_text="Streams", secondary_y=False)
            fig.update_yaxes(title_text="Probabilité algo (%)", secondary_y=True, range=[0, 100])
            st.plotly_chart(fig, width='stretch')
    except Exception as e:
        st.warning(f"Graphique streams/probas indisponible : {e}")

    st.markdown("---")

    # J+28 trajectory (conserved from original)
    st.subheader("🗓️ Trajectoire J+28 (depuis la sortie)")
    try:
        if artist_id:
            df_full = db.fetch_df(
                "SELECT date, streams FROM s4a_song_timeline WHERE song = %s AND artist_id = %s ORDER BY date ASC",
                (track, artist_id)
            )
            df_pop = db.fetch_df(
                "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s AND artist_id = %s ORDER BY date ASC",
                (track, artist_id)
            )
        else:
            df_full = db.fetch_df(
                "SELECT date, streams FROM s4a_song_timeline WHERE song = %s ORDER BY date ASC",
                (track,)
            )
            df_pop = db.fetch_df(
                "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s ORDER BY date ASC",
                (track,)
            )

        if not df_full.empty:
            df_full["date"] = pd.to_datetime(df_full["date"])
            # Use actual release_date from tracks table; fall back to timeline min only if unavailable
            rd = pd.Timestamp(release_date) if release_date else df_full["date"].min()
            end_28 = rd + timedelta(days=28)
            df_focus = df_full[
                (df_full["date"] >= rd) & (df_full["date"] <= end_28)
            ].copy()
            df_focus["day_index"] = (df_focus["date"] - rd).dt.days
            df_focus["streams_cumul"] = df_focus["streams"].cumsum()

            if not df_pop.empty:
                df_pop["date"] = pd.to_datetime(df_pop["date"])
                df_focus = pd.merge(df_focus, df_pop, on="date", how="left")
                df_focus["popularity"] = df_focus["popularity"].ffill().fillna(0)
            else:
                df_focus["popularity"] = 0

            current_total = float(df_focus["streams_cumul"].max())
            days_elapsed = int(df_focus["day_index"].max()) if not df_focus.empty else 0

            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig2.add_trace(go.Scatter(
                x=df_focus["day_index"], y=df_focus["streams_cumul"],
                name="Streams Cumulés", mode="lines+markers",
                line=dict(color="#1DB954", width=3), fill="tozeroy"
            ), secondary_y=False)
            fig2.add_trace(go.Scatter(
                x=df_focus["day_index"], y=df_focus["popularity"],
                name="Index Popularité", mode="lines",
                line=dict(color="#ffffff", width=2, dash="dot")
            ), secondary_y=True)
            # Elbow thresholds (training distribution, 28j) — solid lines, much
            # lower than the round heuristics: this is the honest model cut-off.
            fig2.add_hline(y=ELBOW_THRESHOLDS_28D["RR"], line_dash="solid", line_color="orange",
                           annotation_text=f"RR elbow ({ELBOW_THRESHOLDS_28D['RR']})", secondary_y=False)
            fig2.add_hline(y=ELBOW_THRESHOLDS_28D["RADIO"], line_dash="solid", line_color="#FFE66D",
                           annotation_text=f"Radio elbow ({ELBOW_THRESHOLDS_28D['RADIO']})", secondary_y=False)
            fig2.add_hline(y=ELBOW_THRESHOLDS_28D["DW"], line_dash="solid", line_color="cyan",
                           annotation_text=f"DW elbow ({ELBOW_THRESHOLDS_28D['DW']})", secondary_y=False)
            # Legacy round-number heuristic goals — dashed lines for continuity.
            fig2.add_hline(y=HEURISTIC_GOALS["RR"], line_dash="dash", line_color="orange",
                           annotation_text=f"RR heuristique ({HEURISTIC_GOALS['RR']:,})", secondary_y=False)
            fig2.add_hline(y=HEURISTIC_GOALS["DW"], line_dash="dash", line_color="cyan",
                           annotation_text=f"DW heuristique ({HEURISTIC_GOALS['DW']:,})", secondary_y=False)
            fig2.update_layout(
                title=f"Trajectoire de '{track}' (28 premiers jours)",
                xaxis_title="Jours depuis la sortie (J+)",
                hovermode="x unified", height=550,
                legend=dict(orientation="h", y=1.12)
            )
            fig2.update_yaxes(title_text="Volume Streams", secondary_y=False)
            fig2.update_yaxes(title_text="Popularité (0-100)", secondary_y=True, range=[0, 100])
            st.plotly_chart(fig2, width='stretch')

            # Linear projection fallback
            if not ml_pred and 5 <= days_elapsed < 28:
                avg_daily = current_total / days_elapsed
                projected_28 = avg_daily * 28
                st.info(f"🔮 **Projection :** À ce rythme → ~**{projected_28:,.0f} streams** en 28j.")
                if projected_28 > HEURISTIC_GOALS["DW"]:
                    st.success("🌟 Trajectoire favorable pour Discover Weekly.")
                elif projected_28 > HEURISTIC_GOALS["RR"]:
                    st.warning("⚠️ Release Radar probable, Discover Weekly hors de portée sans boost.")
                else:
                    st.error("📉 Trajectoire insuffisante pour les algos majeurs.")
    except Exception as e:
        st.warning(f"Trajectoire J+28 indisponible : {e}")


# ── Tab 3 — Budget & ROI ──────────────────────────────────────────────────────
def _show_budget_tier_selector(db, artist_id):
    """A&R portfolio tool: select the top-N% tracks by score (lift/precision tradeoff)."""
    st.subheader("🎯 Sélection A&R par budget (top-N%)")
    df = _load_scored_tracks(db, artist_id)
    if df is None or len(df) < 3:
        st.info("Outil disponible dès ≥ 3 titres scorés (échelle catalogue). "
                "Lancez le DAG `ml_scoring_daily`.")
        return
    m = ak.ALGO_MODEL_METRICS.get("DW", {})
    n = len(df)
    pct = st.slider("Pousser le top N% par score", 10, 100, 20, step=10,
                    help="Seuil bas → précision haute (peu de gâchis) ; seuil haut → recall élevé.")
    k = max(1, (n * pct + 99) // 100)
    sel = df.head(k)
    c1, c2, c3 = st.columns(3)
    c1.metric("Titres sélectionnés", f"{k}/{n}")
    c2.metric("Précision modèle", f"{m.get('precision', 0) * 100:.0f}%")
    if pct <= 10:
        c3.metric("Lift top-10%", f"×{m.get('lift_top10', 0):.1f}")
    else:
        c3.metric("Recall (rappel)", f"{m.get('recall', 0) * 100:.0f}%")
    st.caption("Budget serré → vise le top 10% (précision quasi parfaite, peu de gâchis). "
               "Gros budget → baisse le seuil pour capter plus d'opportunités (recall ↑, précision ↓).")
    show = sel[["song", "score_20"]].copy()
    show["score_20"] = show["score_20"].fillna(0).round(1)
    show.columns = ["Titre à pousser", "Score /20"]
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
    st.warning(
        f"⚡ Vélocité élevée ({vel:.2f}) sur « {track} » — la Radio (seuil {radio_thr:g}) "
        f"et le DW ({dw_thr:g}) pénalisent l'hyper-croissance (« feu de paille »). Suggestion : "
        f"réduire la dépense de ~30 % ({spent:,.0f} € → {reduced:,.0f} €) pour lisser le trafic."
    )


def _show_tab_budget_roi(db, track: str, artist_id, date_from, date_to):
    _show_budget_tier_selector(db, artist_id)
    st.markdown("---")

    # 1. Budget Meta restant
    st.subheader("💶 Budget Meta Ads")
    try:
        if artist_id:
            budget_row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget), 0), COALESCE(SUM(daily_budget), 0) FROM meta_campaigns WHERE artist_id = %s AND status = 'ACTIVE'",
                (artist_id,)
            )
            spend_row = db.fetch_query(
                "SELECT COALESCE(SUM(spend), 0) FROM meta_insights_performance_day WHERE artist_id = %s AND day_date BETWEEN %s AND %s",
                (artist_id, date_from, date_to)
            )
            streams_row = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline WHERE artist_id = %s AND date BETWEEN %s AND %s",
                (artist_id, date_from, date_to)
            )
        else:
            budget_row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget), 0), COALESCE(SUM(daily_budget), 0) FROM meta_campaigns WHERE status = 'ACTIVE'"
            )
            spend_row = db.fetch_query(
                "SELECT COALESCE(SUM(spend), 0) FROM meta_insights_performance_day WHERE day_date BETWEEN %s AND %s",
                (date_from, date_to)
            )
            streams_row = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline WHERE date BETWEEN %s AND %s",
                (date_from, date_to)
            )

        lifetime_budget = float(budget_row[0][0] or 0)
        total_spend = float(spend_row[0][0] or 0)
        total_streams = int(streams_row[0][0] or 0)
        remaining = max(lifetime_budget - total_spend, 0)

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Budget lifetime alloué", f"{lifetime_budget:,.2f} €")
        b2.metric("Dépensé (période)", f"{total_spend:,.2f} €")
        pct_remaining = f"{remaining / lifetime_budget * 100:.0f}%" if lifetime_budget > 0 else None
        b3.metric("Restant estimé", f"{remaining:,.2f} €", delta=pct_remaining)

        if total_streams > 0 and total_spend > 0:
            cost_per_stream = total_spend / total_streams
            b4.metric("Coût / stream", f"{cost_per_stream:.4f} €")
            st.markdown("**Estimation pour atteindre les seuils :**")
            seuils = {"Release Radar (1k streams)": 1000, "Discover Weekly (10k streams)": 10000}
            est_cols = st.columns(2)
            for i, (label, seuil) in enumerate(seuils.items()):
                cost_est = cost_per_stream * seuil
                with est_cols[i]:
                    if remaining >= cost_est:
                        st.success(f"**{label}**\n\nCoût estimé : {cost_est:.2f} €\n\n✅ Budget suffisant")
                    else:
                        st.error(f"**{label}**\n\nCoût estimé : {cost_est:.2f} €\n\n❌ Manque {cost_est - remaining:.2f} €")
        else:
            b4.metric("Coût / stream", "—")
            if lifetime_budget == 0:
                st.info("Aucune campagne Meta active trouvée pour cet artiste.")

        if total_spend > 0:
            _show_velocity_budget_advice(db, track, artist_id, total_spend)
    except Exception as e:
        st.warning(f"Budget Meta indisponible : {e}")

    st.markdown("---")

    # 1bis. Organic scaling threshold (volume) — static target until Phase 2 data.
    st.subheader("🔊 Seuil de scaling organique (volume DW)")
    _scale = ak.volume_scaling_threshold("DW")
    if _scale:
        st.info(
            f"Pour déclencher le **scaling de volume** du Discover Weekly, vise un socle "
            f"d'au moins **~{_scale:,} streams organiques/28j** (recherche, profil — hors "
            f"autoplay). Sous ce seuil, l'impact sur le volume est plat ; au-delà, Spotify "
            f"« ouvre les vannes » et multiplie le débit."
        )
        st.caption(
            "⚠️ La valeur organique live (NonAlgoStreams par source) n'est pas encore "
            "collectée (Phase 2 — split par source S4A) : ce seuil est affiché comme "
            "**cible**, pas comme un écart calculé sur vos données."
        )
    st.markdown("---")

    # 2. Groover / Fluence simulator
    with st.expander("💶 Budget playlist — Groover & Fluence", expanded=False):
        _PLATFORMS = [
            {"Plateforme": "Groover",  "Offre": "Standard",  "Coût/soumission (€)": 2.10},
            {"Plateforme": "Groover",  "Offre": "Premium",   "Coût/soumission (€)": 6.00},
            {"Plateforme": "Fluence",  "Offre": "Standard",  "Coût/soumission (€)": 1.50},
            {"Plateforme": "Fluence",  "Offre": "Premium",   "Coût/soumission (€)": 3.00},
        ]
        st.caption("Tarifs de référence — vérifiez les prix actuels sur les plateformes.")
        st.dataframe(pd.DataFrame(_PLATFORMS), hide_index=True, width='stretch')
        st.markdown("**Simulateur de budget**")
        budget_key = f"budget_{track}"
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            total_budget = st.number_input(
                "Budget total (€)", min_value=0.0, value=st.session_state.get(budget_key, 50.0),
                step=5.0, format="%.2f", key=f"budget_input_{track}"
            )
            st.session_state[budget_key] = total_budget
        with col_b2:
            platform_choice = st.selectbox(
                "Plateforme",
                ["Groover Standard (2.10€)", "Groover Premium (6€)",
                 "Fluence Standard (1.50€)", "Fluence Premium (3€)"],
                key=f"plat_{track}"
            )
        with col_b3:
            already_spent = st.number_input(
                "Déjà dépensé (€)", min_value=0.0, value=0.0,
                step=1.0, format="%.2f", key=f"spent_{track}"
            )
        rate_map = {
            "Groover Standard (2.10€)": 2.10, "Groover Premium (6€)": 6.00,
            "Fluence Standard (1.50€)": 1.50, "Fluence Premium (3€)": 3.00,
        }
        rate = rate_map[platform_choice]
        rem = max(total_budget - already_spent, 0.0)
        submissions = int(rem / rate) if rate > 0 else 0
        r1, r2, r3 = st.columns(3)
        r1.metric("Budget restant", f"{rem:.2f} €")
        r2.metric("Coût / soumission", f"{rate:.2f} €")
        r3.metric("Soumissions possibles", submissions)
        if submissions == 0:
            st.warning("Budget insuffisant pour une soumission supplémentaire.")
        else:
            st.success(f"Vous pouvez encore soumettre à **{submissions}** curators sur {platform_choice.split(' (')[0]}.")

    st.markdown("---")

    # 3. ROI regression
    st.subheader("📉 ROI — Régression linéaire (mensuel)")
    try:
        from scipy import stats as sp_stats
        from src.dashboard.utils.kpi_helpers import get_monthly_roi_series

        df_roi = get_monthly_roi_series(db, artist_id, date_from, date_to)
        if df_roi is not None and not df_roi.empty:
            df_roi = df_roi.dropna(subset=["meta_spend", "revenue_eur"])
            df_valid = df_roi[(df_roi["meta_spend"] > 0) | (df_roi["revenue_eur"] > 0)]
            if len(df_valid) >= 2:
                x = df_valid["meta_spend"].astype(float).values
                y = df_valid["revenue_eur"].astype(float).values
                slope, intercept, r_value, p_value, _ = sp_stats.linregress(x, y)
                r2 = r_value ** 2
                x_line = np.linspace(x.min(), x.max(), 100)
                y_line = slope * x_line + intercept

                labels = df_valid["period_date"].astype(str).str[:7] if "period_date" in df_valid.columns else None
                fig_roi = go.Figure()
                fig_roi.add_trace(go.Scatter(
                    x=x, y=y, mode="markers+text",
                    text=labels, textposition="top center",
                    name="Mensuel", marker=dict(color="#1DB954", size=10)
                ))
                fig_roi.add_trace(go.Scatter(
                    x=x_line, y=y_line, mode="lines",
                    name=f"Régression (R²={r2:.2f})",
                    line=dict(color="#FF6B6B", width=2, dash="dash")
                ))
                fig_roi.add_annotation(
                    x=x.max(), y=y_line[-1],
                    text=f"y = {slope:.2f}x + {intercept:.2f}<br>R² = {r2:.2f}",
                    showarrow=False, bgcolor="#222", font=dict(color="white"), bordercolor="#555"
                )
                fig_roi.update_layout(
                    title="Revenue iMusician (€) vs Spend Meta Ads (€)",
                    xaxis_title="Dépenses Meta Ads (€)", yaxis_title="Revenus iMusician (€)",
                    height=420, hovermode="closest"
                )
                st.plotly_chart(fig_roi, width='stretch')
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("R²", f"{r2:.3f}", help="1.0 = corrélation parfaite spend↔revenue")
                rc2.metric("Pente", f"{slope:.2f} €/€", help="Revenue généré par € investi en Meta Ads")
                rc3.metric("p-value", f"{p_value:.3f}", help="< 0.05 = corrélation statistiquement significative")
            else:
                st.info("Données insuffisantes (minimum 2 mois avec spend + revenue).")
        else:
            st.info("Pas de données revenue/spend pour calculer la régression ROI.")
    except ImportError:
        st.warning("scipy non disponible — régression désactivée.")
    except Exception as e:
        st.warning(f"Graphique ROI indisponible : {e}")

    st.markdown("---")

    # 4. Breakeven
    st.subheader("⚖️ Breakeven — Cumul spend vs Cumul revenue")
    try:
        if artist_id:
            df_spend_d = db.fetch_df(
                "SELECT day_date AS date, SUM(spend) AS spend FROM meta_insights_performance_day WHERE artist_id = %s GROUP BY day_date ORDER BY day_date",
                (artist_id,)
            )
            df_rev = db.fetch_df(
                "SELECT make_date(year, month, 1) AS date, revenue_eur FROM imusician_monthly_revenue WHERE artist_id = %s ORDER BY year, month",
                (artist_id,)
            )
            df_pop_be = db.fetch_df(
                "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s AND artist_id = %s ORDER BY date",
                (track, artist_id)
            )
        else:
            df_spend_d = db.fetch_df(
                "SELECT day_date AS date, SUM(spend) AS spend FROM meta_insights_performance_day GROUP BY day_date ORDER BY day_date"
            )
            df_rev = db.fetch_df(
                "SELECT make_date(year, month, 1) AS date, SUM(revenue_eur) AS revenue_eur FROM imusician_monthly_revenue GROUP BY year, month ORDER BY year, month"
            )
            df_pop_be = db.fetch_df(
                "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s ORDER BY date",
                (track,)
            )

        if not df_spend_d.empty and not df_rev.empty:
            df_spend_d["date"] = pd.to_datetime(df_spend_d["date"])
            df_rev["date"] = pd.to_datetime(df_rev["date"])
            all_dates = pd.date_range(
                start=min(df_spend_d["date"].min(), df_rev["date"].min()),
                end=max(df_spend_d["date"].max(), df_rev["date"].max()),
                freq="D"
            )
            df_tl = pd.DataFrame({"date": all_dates})
            df_tl = df_tl.merge(df_spend_d, on="date", how="left")
            df_tl = df_tl.merge(df_rev.rename(columns={"revenue_eur": "revenue"}), on="date", how="left")
            df_tl["spend"] = df_tl["spend"].fillna(0)
            df_tl["revenue"] = df_tl["revenue"].fillna(0)
            df_tl["cumul_spend"] = df_tl["spend"].cumsum()
            df_tl["cumul_revenue"] = df_tl["revenue"].cumsum()

            breakeven_date = None
            for _, row in df_tl.iterrows():
                if row["cumul_spend"] > 0 and row["cumul_revenue"] >= row["cumul_spend"]:
                    breakeven_date = row["date"]
                    break

            fig_be = make_subplots(specs=[[{"secondary_y": True}]])
            fig_be.add_trace(go.Scatter(
                x=df_tl["date"], y=df_tl["cumul_spend"], name="Cumul Spend Meta",
                mode="lines", line=dict(color="#FF6B6B", width=2),
                fill="tozeroy", fillcolor="rgba(255,107,107,0.08)"
            ), secondary_y=False)
            fig_be.add_trace(go.Scatter(
                x=df_tl["date"], y=df_tl["cumul_revenue"], name="Cumul Revenue iMusician",
                mode="lines", line=dict(color="#1DB954", width=2),
                fill="tozeroy", fillcolor="rgba(29,185,84,0.08)"
            ), secondary_y=False)

            if not df_pop_be.empty:
                df_pop_be["date"] = pd.to_datetime(df_pop_be["date"])
                fig_be.add_trace(go.Scatter(
                    x=df_pop_be["date"], y=df_pop_be["popularity"],
                    name="Popularité (0-100)", mode="lines",
                    line=dict(color="#FFE66D", width=1, dash="dot")
                ), secondary_y=True)

            if breakeven_date:
                fig_be.add_vline(
                    x=breakeven_date.timestamp() * 1000,
                    line_dash="dash", line_color="white",
                    annotation_text=f"Breakeven : {breakeven_date.strftime('%d/%m/%Y')}",
                    annotation_position="top right"
                )
                st.success(f"✅ Breakeven atteint le **{breakeven_date.strftime('%d/%m/%Y')}**")
            else:
                st.warning("⚠️ Breakeven non atteint sur la période disponible.")

            fig_be.update_layout(
                title="Cumul spend Meta vs Cumul revenue iMusician",
                hovermode="x unified", height=460,
                legend=dict(orientation="h", y=1.12)
            )
            fig_be.update_yaxes(title_text="Montant cumulé (€)", secondary_y=False)
            fig_be.update_yaxes(title_text="Popularité (0-100)", secondary_y=True, range=[0, 100])
            st.plotly_chart(fig_be, width='stretch')
        else:
            st.info("Données spend ou revenue manquantes pour le graphique breakeven.")
    except Exception as e:
        st.warning(f"Graphique breakeven indisponible : {e}")


# ── Tab 4 — Explainabilité SHAP ───────────────────────────────────────────────
def _show_tab_explainability(ml_pred, track: str):
    if not ml_pred:
        st.info("Aucune prédiction ML disponible pour ce titre. Lancez le DAG `ml_scoring_daily`.")
        return

    features_json = ml_pred.get("features_json")
    if not features_json:
        st.warning("features_json absent de la prédiction ML.")
        _show_key_factors(None)
        return

    try:
        feats = json.loads(features_json) if isinstance(features_json, str) else features_json
    except Exception:
        st.warning("Impossible de parser features_json.")
        return

    try:
        from src.utils.ml_inference import FEATURE_COLUMNS
    except Exception as e:
        st.warning(f"ml_inference non disponible : {e}")
        _show_key_factors(features_json)
        return

    _show_imputation_caveat(feats, FEATURE_COLUMNS)

    _calib = ak.calibration_note("DW", ml_pred.get("dw_probability"))
    if _calib:
        st.info(f"📖 Lecture des probabilités (modèle non calibré) : {_calib}")

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
        st.warning(
            "Bibliothèque `shap` non installée. Ajoutez `shap>=0.44.0` dans requirements.txt "
            "puis reconstruisez l'image Docker (`docker-compose build && docker-compose up -d`)."
        )
    else:
        X_df = pd.DataFrame(
            [[float(feats.get(f, 0.0)) for f in FEATURE_COLUMNS]],
            columns=FEATURE_COLUMNS
        )
        for model_key, algo_label in [
            ("dw_classifier", "Discover Weekly"),
            ("rr_classifier", "Release Radar"),
        ]:
            with st.expander(f"🔍 SHAP Waterfall — {algo_label}",
                             expanded=(model_key == "dw_classifier")):
                model = _load_xgb_model(model_key)
                if model is None:
                    st.warning(f"Modèle `{model_key}` introuvable dans machine_learning/mlruns/.")
                    continue
                try:
                    explainer = shap.TreeExplainer(model)
                    shap_exp = explainer(X_df)
                    shap.plots.waterfall(shap_exp[0], max_display=13, show=False)
                    st.pyplot(plt.gcf(), clear_figure=True)
                    st.caption(
                        "Valeurs SHAP en espace log-odds (modèle non calibré). "
                        "Barres rouges = contribution positive au score, bleues = négative."
                    )
                except Exception as e:
                    st.warning(f"SHAP {algo_label} : {e}")

        # Regressor (volume) waterfall + natural-language autopsy. The forecast is a
        # FLOOR: its SHAP "receipt" explains why the conservative volume is what it is.
        with st.expander("🧾 Autopsie du VOLUME prédit (régresseur DW) — plancher", expanded=False):
            ml_widgets.render_regressor_badge("DW")
            reg = _load_xgb_model("dw_regressor")
            if reg is None:
                st.warning("Modèle `dw_regressor` introuvable dans machine_learning/mlruns/.")
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
                        "Discover Weekly (volume)", baseline, max(0.0, prediction), contributions)
                    st.caption("Valeurs SHAP en streams 7j. À lire comme un plancher : "
                               "le régresseur sous-estime les hits (voir badge ci-dessus).")
                except Exception as e:
                    st.warning(f"SHAP régresseur DW : {e}")

        # Radio volume regressor (MLflow exp 6) — same floor reading. Recent fuel
        # dominates; quality signals (saves, playlist adds) go flat for volume.
        with st.expander("🧾 Autopsie du VOLUME Radio prédit (régresseur) — plancher", expanded=False):
            ml_widgets.render_regressor_badge("RADIO")
            reg = _load_xgb_model("radio_regressor")
            if reg is None:
                st.warning("Modèle `radio_regressor` introuvable dans machine_learning/mlruns/.")
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
                        "Radio (volume)", baseline, max(0.0, prediction), contributions)
                    st.caption("Valeurs SHAP en streams 7j. Le carburant récent domine ; "
                               "saves/playlists sont plats sur le volume (voir badge).")
                except Exception as e:
                    st.warning(f"SHAP régresseur Radio : {e}")

    st.markdown("---")
    st.subheader("🧭 Coach & curseurs de décision par algorithme")
    for _algo in ak.populated_algos():
        st.markdown(f"### {ak.ALGO_LABELS.get(_algo, _algo)}")
        ml_widgets.render_coach(_algo, feats)
        ml_widgets.render_feature_gauges(_algo, feats)
        if _algo in ak.volume_algos():
            ml_widgets.render_volume_gauges(_algo, feats)
        if _algo == "RADIO":
            _recovery = ak.radio_discovery_recovery_note(feats)
            if _recovery:
                st.warning(_recovery)
        st.markdown("---")
    _show_key_factors(features_json)


# ── Tab 5 — Modèle : Actual vs Predicted & Résidus ────────────────────────────
def _show_tab_model(db, track: str, artist_id):
    for _algo in ak.populated_algos():
        if _algo in ak.ALGO_MODEL_METRICS:
            ml_widgets.render_classification_scorecard(_algo, compact=True)
    st.markdown("---")
    st.subheader("📊 Actual vs Predicted — Streams 7j")
    try:
        if artist_id:
            df_hist = db.fetch_df(
                """SELECT prediction_date, streams_7d AS actual,
                          dw_streams_forecast_7d AS predicted_dw,
                          rr_streams_forecast_7d AS predicted_rr,
                          radio_streams_forecast_7d AS predicted_radio
                   FROM ml_song_predictions
                   WHERE song = %s AND artist_id = %s AND streams_7d IS NOT NULL
                   ORDER BY prediction_date ASC LIMIT 60""",
                (track, artist_id)
            )
        else:
            df_hist = db.fetch_df(
                """SELECT prediction_date, streams_7d AS actual,
                          dw_streams_forecast_7d AS predicted_dw,
                          rr_streams_forecast_7d AS predicted_rr,
                          radio_streams_forecast_7d AS predicted_radio
                   FROM ml_song_predictions
                   WHERE song = %s AND streams_7d IS NOT NULL
                   ORDER BY prediction_date ASC LIMIT 60""",
                (track,)
            )

        if df_hist.empty or len(df_hist) < 2:
            st.info("Historique insuffisant (minimum 2 prédictions avec streams_7d renseigné).")
            return

        df_hist = df_hist.dropna(subset=["actual", "predicted_dw"])
        df_hist["prediction_date"] = pd.to_datetime(df_hist["prediction_date"])

        col1, col2, col3 = st.columns(3)

        with col1:
            st.write("**DW forecast**")
            max_val = max(float(df_hist["actual"].max()), float(df_hist["predicted_dw"].max()))
            fig_dw = go.Figure()
            fig_dw.add_trace(go.Scatter(
                x=df_hist["predicted_dw"].astype(float),
                y=df_hist["actual"].astype(float),
                mode="markers",
                marker=dict(color="#1DB954", size=8),
                name="Points",
                text=df_hist["prediction_date"].dt.strftime("%Y-%m-%d"),
                hovertemplate="Date: %{text}<br>Forecast DW: %{x:,}<br>Actuel: %{y:,}"
            ))
            fig_dw.add_trace(go.Scatter(
                x=[0, max_val], y=[0, max_val], mode="lines",
                name="Prédiction parfaite",
                line=dict(color="gray", dash="dash", width=1)
            ))
            fig_dw.update_layout(
                xaxis_title="Forecast DW (streams 7j)", yaxis_title="Actuel (streams 7j)",
                height=340, showlegend=True
            )
            st.plotly_chart(fig_dw, width='stretch')

        with col2:
            df_rr = df_hist.dropna(subset=["predicted_rr"])
            if not df_rr.empty:
                st.write("**RR forecast**")
                max_val_rr = max(float(df_rr["actual"].max()), float(df_rr["predicted_rr"].max()))
                fig_rr = go.Figure()
                fig_rr.add_trace(go.Scatter(
                    x=df_rr["predicted_rr"].astype(float),
                    y=df_rr["actual"].astype(float),
                    mode="markers",
                    marker=dict(color="#4ECDC4", size=8),
                    name="Points",
                    text=df_rr["prediction_date"].dt.strftime("%Y-%m-%d"),
                    hovertemplate="Date: %{text}<br>Forecast RR: %{x:,}<br>Actuel: %{y:,}"
                ))
                fig_rr.add_trace(go.Scatter(
                    x=[0, max_val_rr], y=[0, max_val_rr], mode="lines",
                    name="Prédiction parfaite",
                    line=dict(color="gray", dash="dash", width=1)
                ))
                fig_rr.update_layout(
                    xaxis_title="Forecast RR (streams 7j)", yaxis_title="Actuel (streams 7j)",
                    height=340, showlegend=True
                )
                st.plotly_chart(fig_rr, width='stretch')
                if not ak.volume_forecast_reliable("RR"):
                    st.caption("⚠️ R²=0.32 — diagnostic uniquement, PAS une prévision. "
                               "Le volume Release Radar n'est pas prédictible (bruit lié "
                               "au taux d'ouverture des notifications).")
            else:
                st.info("Pas de prédictions RR disponibles pour ce titre.")

        with col3:
            df_radio = (df_hist.dropna(subset=["predicted_radio"])
                        if "predicted_radio" in df_hist.columns else df_hist.iloc[0:0])
            if not df_radio.empty:
                st.write("**Radio forecast**")
                max_val_radio = max(float(df_radio["actual"].max()),
                                    float(df_radio["predicted_radio"].max()))
                fig_radio = go.Figure()
                fig_radio.add_trace(go.Scatter(
                    x=df_radio["predicted_radio"].astype(float),
                    y=df_radio["actual"].astype(float),
                    mode="markers",
                    marker=dict(color="#FFA500", size=8),
                    name="Points",
                    text=df_radio["prediction_date"].dt.strftime("%Y-%m-%d"),
                    hovertemplate="Date: %{text}<br>Forecast Radio: %{x:,}<br>Actuel: %{y:,}"
                ))
                fig_radio.add_trace(go.Scatter(
                    x=[0, max_val_radio], y=[0, max_val_radio], mode="lines",
                    name="Prédiction parfaite",
                    line=dict(color="gray", dash="dash", width=1)
                ))
                fig_radio.update_layout(
                    xaxis_title="Forecast Radio (streams 7j)", yaxis_title="Actuel (streams 7j)",
                    height=340, showlegend=True
                )
                st.plotly_chart(fig_radio, width='stretch')
            else:
                st.info("Pas de prédictions Radio disponibles pour ce titre.")

        st.markdown("---")
        st.subheader("📉 Résidus dans le temps (Actuel − Forecast DW)")
        df_hist["residual"] = df_hist["actual"].astype(float) - df_hist["predicted_dw"].astype(float)
        colors = ["#1DB954" if r >= 0 else "#FF6B6B" for r in df_hist["residual"]]

        fig_res = go.Figure()
        fig_res.add_trace(go.Bar(
            x=df_hist["prediction_date"], y=df_hist["residual"],
            marker_color=colors, name="Résidu",
            hovertemplate="Date: %{x}<br>Résidu: %{y:,.0f}"
        ))
        fig_res.add_hline(y=0, line_color="white", line_width=1)
        fig_res.update_layout(
            title="Vert = sous-prédit (actuel > forecast) | Rouge = sur-prédit",
            xaxis_title="Date de prédiction",
            yaxis_title="Actuel − Forecast DW (streams)",
            height=340, hovermode="x unified"
        )
        st.plotly_chart(fig_res, width='stretch')

        mean_res = df_hist["residual"].mean()
        std_res = df_hist["residual"].std()
        st.caption(f"Biais moyen : {mean_res:,.0f} streams | Écart-type : {std_res:,.0f} streams")
        if len(df_hist) >= 3 and abs(mean_res) > std_res:
            st.warning("Biais systématique détecté — le modèle sur- ou sous-prédit de façon consistante pour ce titre.")

    except Exception as e:
        st.warning(f"Graphique Actual vs Predicted indisponible : {e}")


# ── Tab 6 — Cycle de vie & Benchmark ──────────────────────────────────────────
# (label, order, lower_week_inclusive, upper_week_exclusive)
_LIFECYCLE_AGE_BINS = [
    ("0-5", 1, 0, 5), ("5-10", 2, 5, 10), ("10-25", 3, 10, 25),
    ("25-50", 4, 25, 50), ("50-100", 5, 50, 100), ("100+", 6, 100, 10**9),
]
_LIFECYCLE_PALETTE = {"DW": "rgb(0,200,220)", "RR": "rgb(255,165,0)", "RADIO": "rgb(29,185,84)"}
_LIFECYCLE_LABELS = {"DW": "💎 Discover Weekly", "RR": "📡 Release Radar", "RADIO": "📻 Radio"}


@st.cache_data(ttl=3600)
def _load_lifecycle_benchmark(_db, dataset_version="v1"):
    """Load the GLOBAL cohort lifecycle curves. `_db` underscored → not hashed."""
    try:
        return _db.fetch_df(
            """SELECT algorithm, age_week_bin, age_week_bin_order,
                      ratio_q1, ratio_median, ratio_q3,
                      total_stream_median, sample_count
               FROM algo_lifecycle_benchmark
               WHERE dataset_version = %s
               ORDER BY age_week_bin_order""",
            (dataset_version,),
        )
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
                             fill="tonexty", fillcolor=rgba, name="P25–P75 (cohorte)"))
    fig.add_trace(go.Scatter(x=x, y=curve_df["ratio_median"], mode="lines+markers",
                             line=dict(color=color, width=3), name="Médiane cohorte"))
    fig.add_hline(y=1.0, line_dash="dot", line_color="grey",
                  annotation_text="Moyenne catégorie (1.0×)")
    if live_order is not None:
        fig.add_vline(x=live_order, line_dash="dash", line_color="#ffffff",
                      annotation_text="Ce titre", annotation_position="top")
    fig.update_layout(title=f"{algo_label} — ratio de standardisation par âge",
                      height=300, xaxis_title="Âge du titre (semaines)",
                      yaxis_title="Ratio (titre / moyenne catégorie)",
                      hovermode="x unified", legend=dict(orientation="h", y=1.18),
                      margin=dict(t=70))
    fig.update_xaxes(tickmode="array", tickvals=x, ticktext=list(curve_df["age_week_bin"]))
    return fig


def _standardization_block(db, track, artist_id, age_weeks, benchmark_df):
    st.markdown("#### 📍 Position de ce titre vs cohorte")
    if age_weeks is None:
        st.info("Date de sortie inconnue — impossible de situer le titre.")
        return
    order, bin_label = _age_week_order(age_weeks)
    ref = benchmark_df[benchmark_df["age_week_bin_order"] == order]["total_stream_median"].dropna()
    if ref.empty:
        st.info(
            f"Âge : **{age_weeks} sem.** (tranche {bin_label}). Référence cohorte "
            "total-streams indisponible (artefact provisoire) — seul l'âge est "
            "superposé sur les courbes ci-dessus."
        )
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
        st.info("Streams du titre indisponibles.")
        return
    cohort_med = float(ref.iloc[0])
    ratio = live_28d / cohort_med if cohort_med > 0 else 0.0
    st.metric(f"Position vs cohorte (tranche {bin_label})", f"{ratio:.2f}×",
              delta=f"{(ratio - 1) * 100:+.0f}% vs médiane")
    st.caption(
        "Ratio basé sur le **total** des streams (toutes sources, 28j). La "
        "répartition par algorithme provient de la cohorte globale et n'est PAS "
        "mesurée sur ce titre."
    )


def _lifecycle_legend():
    with st.expander("ℹ️ Comprendre les courbes de vie & la standardisation", expanded=False):
        st.markdown(
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
        )


def _show_tab_lifecycle(db, track, artist_id, release_date, benchmark_df):
    st.subheader("📉 Cycle de vie algorithmique & standardisation")
    if show_empty_state(
        benchmark_df,
        "Benchmark indisponible — artefact non généré "
        "(voir migration 035 / export_lifecycle_benchmark.py).",
        level="warning",
    ):
        return

    age_weeks = _compute_age_weeks(release_date)
    live_order, live_bin = _age_week_order(age_weeks)
    c1, c2 = st.columns([1, 2])
    c1.metric("Âge du titre", f"{age_weeks} sem." if age_weeks is not None else "—")
    c2.caption(f"Sortie : {release_date or '—'} · tranche {live_bin or '—'} · "
               "courbes = cohorte globale statique")
    _lifecycle_legend()

    for algo in ("DW", "RR", "RADIO"):
        curve = benchmark_df[benchmark_df["algorithm"] == algo].sort_values("age_week_bin_order")
        if curve.empty:
            continue
        st.plotly_chart(
            _lifecycle_band_fig(curve, _LIFECYCLE_LABELS[algo], live_order, _LIFECYCLE_PALETTE[algo]),
            width="stretch",
        )

    st.markdown("---")
    _standardization_block(db, track, artist_id, age_weeks, benchmark_df)
    st.divider()
    with st.expander("🗒️ Notes & analyses à venir"):
        st.caption("Espace réservé pour intégrer les prochaines analyses "
                   "(distribution complète en boxplots, segmentation par décile, etc.).")


# ── Entrypoint ────────────────────────────────────────────────────────────────
def show():
    from src.dashboard.auth import require_plan
    if not require_plan('basic'):
        return

    st.title("🚀 Road to Algorithms (J+28)")
    st.markdown("Suivi ML, budget, ROI et explainabilité des scores algorithmiques.")

    with view_session() as (db, artist_id):
        # Track list — ordered by release_date DESC from tracks table.
        # S4A CSVs replace '?' with '_' in song names, so the JOIN uses REPLACE().
        try:
            if artist_id:
                tracks = db.fetch_df(
                    """SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s AND artist_id = %s GROUP BY song) t
                       LEFT JOIN tracks tk ON REPLACE(tk.track_name, '?', '_') = t.song
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%", artist_id)
                )["song"].tolist()
            else:
                tracks = db.fetch_df(
                    """SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s GROUP BY song) t
                       LEFT JOIN tracks tk ON REPLACE(tk.track_name, '?', '_') = t.song
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%",)
                )["song"].tolist()
        except Exception:
            tracks = []

        if not tracks:
            st.warning("Aucune donnée de timeline disponible.")
            return

        # Global selectors
        today = date.today()
        sel1, sel2 = st.columns([2, 2])
        with sel1:
            selected_track = st.selectbox("🎵 Titre", tracks)

        # Fetch release_date of selected track via tracks table (same '?' → '_' normalisation)
        try:
            rd_rows = db.fetch_query(
                "SELECT release_date FROM tracks WHERE REPLACE(track_name, '?', '_') = %s LIMIT 1",
                (selected_track,)
            )
            track_release_date = rd_rows[0][0] if rd_rows and rd_rows[0][0] else (today - timedelta(days=28))
        except Exception:
            track_release_date = today - timedelta(days=28)

        with sel2:
            _PRESETS = [
                "28 derniers jours",
                "90 derniers jours",
                "Mois en cours",
                "Mois précédent",
                "Mois / Année",
                "Personnalisé",
            ]
            period_preset = st.selectbox(
                "📅 Période",
                _PRESETS,
                key=f"period_preset_{selected_track}"
            )

        # Sub-selectors rendered below the two-column row (full width)
        import calendar as _cal
        _MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                   "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

        if period_preset == "28 derniers jours":
            date_from, date_to = today - timedelta(days=28), today

        elif period_preset == "90 derniers jours":
            date_from, date_to = today - timedelta(days=90), today

        elif period_preset == "Mois en cours":
            date_from = today.replace(day=1)
            date_to = today

        elif period_preset == "Mois précédent":
            first_current = today.replace(day=1)
            date_to = first_current - timedelta(days=1)
            date_from = date_to.replace(day=1)

        elif period_preset == "Mois / Année":
            cm, cy = st.columns([1, 1])
            sel_month = cm.selectbox(
                "Mois", _MONTHS,
                index=today.month - 1,
                key=f"sel_month_{selected_track}"
            )
            sel_year = cy.selectbox(
                "Année",
                list(range(2022, today.year + 1))[::-1],
                key=f"sel_year_{selected_track}"
            )
            month_num = _MONTHS.index(sel_month) + 1
            date_from = date(sel_year, month_num, 1)
            last_day = _cal.monthrange(sel_year, month_num)[1]
            date_to = min(date(sel_year, month_num, last_day), today)

        else:  # Personnalisé
            _custom = st.date_input(
                "Plage personnalisée",
                value=(today - timedelta(days=28), today),
                max_value=today,
                key=f"period_custom_{selected_track}"
            )
            if isinstance(_custom, (list, tuple)) and len(_custom) == 2:
                date_from, date_to = _custom[0], _custom[1]
            else:
                date_from, date_to = today - timedelta(days=28), today

        # Load ML prediction + global benchmark once — shared across tabs
        ml_pred = _load_ml_pred(db, selected_track, artist_id)
        benchmark_df = _load_lifecycle_benchmark(db)

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "🎯 Vue Globale",
            "📊 Suivi Algorithmes",
            "💰 Budget & ROI",
            "🔍 Explainabilité",
            "📈 Modèle",
            "📉 Cycle de vie & Benchmark",
        ])
        with tab1:
            _show_tab_global(db, selected_track, artist_id, date_from, date_to, ml_pred, release_date=track_release_date)
        with tab2:
            _show_tab_algos(db, selected_track, artist_id, date_from, date_to, ml_pred, release_date=track_release_date)
        with tab3:
            _show_tab_budget_roi(db, selected_track, artist_id, date_from, date_to)
        with tab4:
            _show_tab_explainability(ml_pred, selected_track)
        with tab5:
            _show_tab_model(db, selected_track, artist_id)
        with tab6:
            _show_tab_lifecycle(db, selected_track, artist_id,
                                release_date=track_release_date, benchmark_df=benchmark_df)
