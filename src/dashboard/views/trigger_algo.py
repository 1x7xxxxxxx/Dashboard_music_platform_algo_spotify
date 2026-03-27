"""Vue Road to Algorithms — scoring ML, suivi, budget, SHAP, ROI.

Type: Feature
Uses: ml_song_predictions, s4a_song_timeline, s4a_audience, s4a_songs_global,
      meta_campaigns, meta_insights_performance_day, imusician_monthly_revenue,
      track_popularity_history
Depends on: get_db_connection, kpi_helpers.get_monthly_roi_series,
            ml_inference.FEATURE_COLUMNS / MODEL_PATHS / _resolve_path
"""
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta

from src.dashboard.utils import get_db_connection


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
        st.caption(f"Forecast streams 7j si activé : ~{forecast:,}")


def _show_ml_section(pred: dict):
    pred_date = pred.get("prediction_date", "—")
    model_v = pred.get("model_version", "v1")
    st.caption(f"Prédiction ML du **{pred_date}** — modèle `{model_v}`")
    _display_prob_bar("📡 Release Radar", pred.get("rr_probability"), pred.get("rr_streams_forecast_7d"))
    _display_prob_bar("💎 Discover Weekly", pred.get("dw_probability"), pred.get("dw_streams_forecast_7d"))
    _display_prob_bar("📻 Radio Spotify", pred.get("radio_probability"))


def _show_heuristic_section(current_total: float, current_pop: float):
    st.info("⚠️ **Mode Heuristique** — Aucune prédiction ML disponible. "
            "Lancez le DAG `ml_scoring_daily` pour obtenir des probabilités ML.")
    GOAL_RR = 1000
    GOAL_DW_S = 10000
    GOAL_DW_P = 30
    pct_rr = min(current_total / GOAL_RR, 1.0)
    pct_dw = (min(current_total / GOAL_DW_S, 1.0) + min(current_pop / GOAL_DW_P, 1.0)) / 2
    st.write(f"**📡 Release Radar** ({int(pct_rr * 100)}%)")
    st.progress(pct_rr)
    if pct_rr >= 1.0:
        st.caption("✅ Trigger théoriquement activé !")
    else:
        st.caption(f"Manque {GOAL_RR - current_total:,.0f} streams (seuil heuristique)")
    st.write(f"**💎 Discover Weekly** ({int(pct_dw * 100)}%)")
    st.progress(pct_dw)
    col1, col2 = st.columns(2)
    col1.info(f"Streams : {min(current_total / GOAL_DW_S, 1.0) * 100:.0f}% (obj. 10k)")
    col2.info(f"Popularité : {min(current_pop / GOAL_DW_P, 1.0) * 100:.0f}% (obj. 30)")


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


# ── Data helpers ─────────────────────────────────────────────────────────────
def _load_ml_pred(db, track: str, artist_id) -> dict | None:
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
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
                "prediction_date": r[5], "model_version": r[6], "features_json": r[7],
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


# ── Tab 1 — Vue Globale ───────────────────────────────────────────────────────
def _show_tab_global(db, track: str, artist_id, date_from, date_to, ml_pred):
    st.subheader("📊 Métriques sur la période sélectionnée")

    # Listeners (artist-level, not track-level in s4a_audience)
    try:
        if artist_id:
            listeners = db.fetch_query(
                "SELECT COALESCE(SUM(listeners), 0) FROM s4a_audience WHERE artist_id = %s AND date BETWEEN %s AND %s",
                (artist_id, date_from, date_to)
            )[0][0]
        else:
            listeners = db.fetch_query(
                "SELECT COALESCE(SUM(listeners), 0) FROM s4a_audience WHERE date BETWEEN %s AND %s",
                (date_from, date_to)
            )[0][0]
    except Exception:
        listeners = None

    # Streams (track-level)
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

    # Saves (total from s4a_songs_global — no daily granularity available)
    try:
        if artist_id:
            saves_row = db.fetch_query(
                "SELECT saves FROM s4a_songs_global WHERE song = %s AND artist_id = %s",
                (track, artist_id)
            )
        else:
            saves_row = db.fetch_query(
                "SELECT saves FROM s4a_songs_global WHERE song = %s", (track,)
            )
        saves = int(saves_row[0][0]) if saves_row else None
    except Exception:
        saves = None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Listeners (période)", f"{int(listeners or 0):,}" if listeners is not None else "—")
    col2.metric("Streams titre (période)", f"{int(streams or 0):,}" if streams is not None else "—")
    col3.metric("Saves (total)", f"{int(saves or 0):,}" if saves is not None else "—")
    col4.metric("Playlist adds", "N/A", help="Donnée non collectée dans les CSV S4A")

    st.markdown("---")

    # Score /20 benchmark
    st.subheader("🏆 Score /20 — Benchmark toutes les tracks")
    try:
        if artist_id:
            df_bench = db.fetch_df(
                """SELECT song, dw_probability, rr_probability, radio_probability, streams_28d,
                          CAST(features_json->>'Velocity_Streams' AS FLOAT) AS velocity
                   FROM ml_song_predictions
                   WHERE artist_id = %s AND prediction_date = (
                       SELECT MAX(prediction_date) FROM ml_song_predictions WHERE artist_id = %s
                   )""",
                (artist_id, artist_id)
            )
        else:
            df_bench = db.fetch_df(
                """SELECT song, dw_probability, rr_probability, radio_probability, streams_28d,
                          CAST(features_json->>'Velocity_Streams' AS FLOAT) AS velocity
                   FROM ml_song_predictions
                   WHERE prediction_date = (SELECT MAX(prediction_date) FROM ml_song_predictions)"""
            )

        if not df_bench.empty:
            df_bench = _compute_score_20(df_bench)
            df_bench = df_bench.sort_values("score_20", ascending=False)

            display = df_bench[["song", "score_20", "dw_probability", "rr_probability",
                                "radio_probability", "streams_28d"]].copy()
            display["score_20"] = display["score_20"].round(1)
            display["dw_probability"] = (display["dw_probability"] * 100).round(0).astype("Int64")
            display["rr_probability"] = (display["rr_probability"] * 100).round(0).astype("Int64")
            display["radio_probability"] = (display["radio_probability"] * 100).round(0).astype("Int64")
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
            release_date = df_full["date"].min()
            end_28 = release_date + timedelta(days=28)
            df_28 = df_full[(df_full["date"] >= release_date) & (df_full["date"] <= end_28)].copy()
            df_28["day_index"] = (df_28["date"] - release_date).dt.days
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
def _show_tab_algos(db, track: str, artist_id, date_from, date_to, ml_pred):
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
            release_date = df_full["date"].min()
            end_28 = release_date + timedelta(days=28)
            df_focus = df_full[
                (df_full["date"] >= release_date) & (df_full["date"] <= end_28)
            ].copy()
            df_focus["day_index"] = (df_focus["date"] - release_date).dt.days
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
            fig2.add_hline(y=1000, line_dash="dash", line_color="orange",
                           annotation_text="Seuil Release Radar (1k)", secondary_y=False)
            fig2.add_hline(y=10000, line_dash="dash", line_color="cyan",
                           annotation_text="Seuil DW (10k)", secondary_y=False)
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
                if projected_28 > 10000:
                    st.success("🌟 Trajectoire favorable pour Discover Weekly.")
                elif projected_28 > 1000:
                    st.warning("⚠️ Release Radar probable, Discover Weekly hors de portée sans boost.")
                else:
                    st.error("📉 Trajectoire insuffisante pour les algos majeurs.")
    except Exception as e:
        st.warning(f"Trajectoire J+28 indisponible : {e}")


# ── Tab 3 — Budget & ROI ──────────────────────────────────────────────────────
def _show_tab_budget_roi(db, track: str, artist_id, date_from, date_to):
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
    except Exception as e:
        st.warning(f"Budget Meta indisponible : {e}")

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

    st.markdown("---")
    _show_key_factors(features_json)


# ── Tab 5 — Modèle : Actual vs Predicted & Résidus ────────────────────────────
def _show_tab_model(db, track: str, artist_id):
    st.subheader("📊 Actual vs Predicted — Streams 7j")
    try:
        if artist_id:
            df_hist = db.fetch_df(
                """SELECT prediction_date, streams_7d AS actual,
                          dw_streams_forecast_7d AS predicted_dw,
                          rr_streams_forecast_7d AS predicted_rr
                   FROM ml_song_predictions
                   WHERE song = %s AND artist_id = %s AND streams_7d IS NOT NULL
                   ORDER BY prediction_date ASC LIMIT 60""",
                (track, artist_id)
            )
        else:
            df_hist = db.fetch_df(
                """SELECT prediction_date, streams_7d AS actual,
                          dw_streams_forecast_7d AS predicted_dw,
                          rr_streams_forecast_7d AS predicted_rr
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

        col1, col2 = st.columns(2)

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
            else:
                st.info("Pas de prédictions RR disponibles pour ce titre.")

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


# ── Entrypoint ────────────────────────────────────────────────────────────────
def show():
    st.title("🚀 Road to Algorithms (J+28)")
    st.markdown("Suivi ML, budget, ROI et explainabilité des scores algorithmiques.")

    db = get_db_connection()
    artist_id = st.session_state.get("artist_id")

    try:
        # Track list
        try:
            if artist_id:
                tracks = db.fetch_df(
                    "SELECT song FROM s4a_song_timeline WHERE song NOT ILIKE %s AND artist_id = %s GROUP BY song ORDER BY MIN(date) DESC",
                    ("%1x7xxxxxxx%", artist_id)
                )["song"].tolist()
            else:
                tracks = db.fetch_df(
                    "SELECT song FROM s4a_song_timeline WHERE song NOT ILIKE %s GROUP BY song ORDER BY MIN(date) DESC",
                    ("%1x7xxxxxxx%",)
                )["song"].tolist()
        except Exception:
            tracks = []

        if not tracks:
            st.warning("Aucune donnée de timeline disponible.")
            return

        # Global selectors
        sel1, sel2 = st.columns([2, 2])
        with sel1:
            selected_track = st.selectbox("🎵 Titre", tracks)
        with sel2:
            today = date.today()
            period = st.date_input(
                "📅 Période", value=(today - timedelta(days=28), today),
                max_value=today, key="trigger_period"
            )

        if isinstance(period, (list, tuple)) and len(period) == 2:
            date_from, date_to = period[0], period[1]
        else:
            date_from = today - timedelta(days=28)
            date_to = today

        # Load ML prediction once — shared across tabs
        ml_pred = _load_ml_pred(db, selected_track, artist_id)

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🎯 Vue Globale",
            "📊 Suivi Algorithmes",
            "💰 Budget & ROI",
            "🔍 Explainabilité",
            "📈 Modèle",
        ])
        with tab1:
            _show_tab_global(db, selected_track, artist_id, date_from, date_to, ml_pred)
        with tab2:
            _show_tab_algos(db, selected_track, artist_id, date_from, date_to, ml_pred)
        with tab3:
            _show_tab_budget_roi(db, selected_track, artist_id, date_from, date_to)
        with tab4:
            _show_tab_explainability(ml_pred, selected_track)
        with tab5:
            _show_tab_model(db, selected_track, artist_id)

    finally:
        db.close()
