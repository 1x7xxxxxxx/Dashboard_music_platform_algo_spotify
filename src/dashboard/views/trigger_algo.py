import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.auth import artist_id_sql_filter


# ---------------------------------------------------------------------------
# Labels humains des features ML + direction (True = valeur haute = bien)
# ---------------------------------------------------------------------------
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


def _display_prob_bar(label: str, prob: float | None, forecast: int | None = None):
    """Affiche une barre de progression ML avec indicateur coloré."""
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
    """Affiche les probabilités algorithmiques depuis une prédiction ML."""
    pred_date = pred.get("prediction_date", "—")
    model_v = pred.get("model_version", "v1")
    st.caption(f"Prédiction ML du **{pred_date}** — modèle `{model_v}`")

    _display_prob_bar("📡 Release Radar", pred.get("rr_probability"), pred.get("rr_streams_forecast_7d"))
    _display_prob_bar("💎 Discover Weekly", pred.get("dw_probability"), pred.get("dw_streams_forecast_7d"))
    _display_prob_bar("📻 Radio Spotify", pred.get("radio_probability"))


def _show_heuristic_section(current_total: float, current_pop: float):
    """Fallback : barres heuristiques hardcodées."""
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
    """Top 3 points forts / à améliorer depuis features_json."""
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
        # Point fort = valeur haute si high_is_good, ou valeur basse si not high_is_good
        is_positive = (val > 0.5 and high_is_good) or (val <= 0.5 and not high_is_good)
        # Valeur affichée : dé-log si feature log-transformée
        if "_log" in key:
            display = f"{int(np.expm1(val)):,}"
        elif key == "DaysSinceRelease":
            display = f"{int(val)} jours"
        elif key in ("ReleasePhaseEarly", "IsThisSongOptedIntoSpotifyDiscoveryMode"):
            display = "Oui" if val >= 0.5 else "Non"
        else:
            display = f"{val:.2f}"
        items.append({"label": label, "display": display, "is_positive": is_positive, "val": abs(val)})

    positives = sorted([i for i in items if i["is_positive"]], key=lambda x: x["val"], reverse=True)
    negatives = sorted([i for i in items if not i["is_positive"]], key=lambda x: x["val"], reverse=True)

    st.subheader("🔍 Facteurs clés")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**✅ Points forts**")
        for item in positives[:3]:
            st.success(f"**{item['label']}** : {item['display']}")
        if not positives:
            st.caption("Aucun facteur positif détecté.")
    with col2:
        st.write("**⚠️ Points à améliorer**")
        for item in negatives[:3]:
            st.warning(f"**{item['label']}** : {item['display']}")
        if not negatives:
            st.caption("Aucun facteur négatif détecté.")


def show():
    st.title("🚀 Road to Algorithms (J+28)")
    st.markdown("Suivi de l'activation des algorithmes Spotify avec scoring ML.")

    db = get_db_connection()
    artist_id = st.session_state.get("artist_id")

    # ── 1. Sélection du titre ────────────────────────────────────────────────
    try:
        if artist_id:
            tracks = db.fetch_df(
                """SELECT song FROM s4a_song_timeline
                   WHERE song NOT ILIKE %s AND artist_id = %s
                   GROUP BY song ORDER BY MIN(date) DESC""",
                ("%1x7xxxxxxx%", artist_id)
            )["song"].tolist()
        else:
            tracks = db.fetch_df(
                """SELECT song FROM s4a_song_timeline
                   WHERE song NOT ILIKE %s
                   GROUP BY song ORDER BY MIN(date) DESC""",
                ("%1x7xxxxxxx%",)
            )["song"].tolist()
    except Exception:
        tracks = []

    if not tracks:
        st.warning("Aucune donnée de timeline disponible.")
        db.close()
        return

    selected_track = st.selectbox("Sélectionner un titre", tracks)

    # ── 2. Prédiction ML (dernière en date) ──────────────────────────────────
    ml_pred = None
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE artist_id = %s AND song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (artist_id, selected_track)
            )
        else:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (selected_track,)
            )
        if rows:
            r = rows[0]
            ml_pred = {
                "dw_probability": r[0], "rr_probability": r[1], "radio_probability": r[2],
                "dw_streams_forecast_7d": r[3], "rr_streams_forecast_7d": r[4],
                "prediction_date": r[5], "model_version": r[6], "features_json": r[7],
            }
    except Exception:
        ml_pred = None

    # ── 3. Données streams & popularité (J+28) ───────────────────────────────
    if artist_id:
        df_streams = db.fetch_df(
            "SELECT date, streams FROM s4a_song_timeline WHERE song = %s AND artist_id = %s ORDER BY date ASC",
            (selected_track, artist_id)
        )
        df_pop = db.fetch_df(
            "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s AND artist_id = %s ORDER BY date ASC",
            (selected_track, artist_id)
        )
    else:
        df_streams = db.fetch_df(
            "SELECT date, streams FROM s4a_song_timeline WHERE song = %s ORDER BY date ASC",
            (selected_track,)
        )
        df_pop = db.fetch_df(
            "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s ORDER BY date ASC",
            (selected_track,)
        )

    if df_streams.empty:
        st.error("Pas de données de streams pour ce titre.")
        db.close()
        return

    # Fenêtre J+28
    release_date = pd.to_datetime(df_streams["date"].min())
    end_date_28 = release_date + timedelta(days=28)
    df_streams["date"] = pd.to_datetime(df_streams["date"])
    df_focus = df_streams.loc[
        (df_streams["date"] >= release_date) & (df_streams["date"] <= end_date_28)
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
    current_pop = float(df_focus["popularity"].iloc[-1]) if not df_focus.empty else 0
    days_elapsed = int(df_focus["day_index"].max()) if not df_focus.empty else 0

    # ── 4. KPIs ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Jours écoulés", f"{days_elapsed}/28",
              delta=f"{28 - days_elapsed} restants", delta_color="inverse")
    c2.metric("Streams Cumulés (J+28)", f"{current_total:,.0f}")
    c3.metric("Popularité Actuelle", f"{current_pop:.0f}/100")

    st.markdown("---")

    # ── 5. Probabilités algorithmiques ───────────────────────────────────────
    st.subheader("🎯 Objectifs Algorithmiques")
    if ml_pred:
        _show_ml_section(ml_pred)
    else:
        _show_heuristic_section(current_total, current_pop)

    st.markdown("---")

    # ── 6. Facteurs clés (ML uniquement) ─────────────────────────────────────
    if ml_pred:
        _show_key_factors(ml_pred.get("features_json"))
        st.markdown("---")

    # ── 7. Graphique trajectoire J+28 ────────────────────────────────────────
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=df_focus["day_index"], y=df_focus["streams_cumul"],
        name="Streams Cumulés", mode="lines+markers",
        line=dict(color="#1DB954", width=3), fill="tozeroy"
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df_focus["day_index"], y=df_focus["popularity"],
        name="Index Popularité", mode="lines",
        line=dict(color="#ffffff", width=2, dash="dot")
    ), secondary_y=True)
    fig.add_hline(y=1000, line_dash="dash", line_color="orange",
                  annotation_text="Seuil Release Radar (1k)", secondary_y=False)
    fig.add_hline(y=10000, line_dash="dash", line_color="cyan",
                  annotation_text="Seuil DW (10k)", secondary_y=False)
    fig.update_layout(
        title=f"Trajectoire de '{selected_track}' (28 premiers jours)",
        xaxis_title="Jours depuis la sortie (J+)",
        hovermode="x unified", height=600,
        legend=dict(orientation="h", y=1.1)
    )
    fig.update_yaxes(title_text="Volume Streams", secondary_y=False)
    fig.update_yaxes(title_text="Popularité (0-100)", secondary_y=True, range=[0, 100])
    st.plotly_chart(fig, width="stretch")

    # ── 8. Projection linéaire (heuristique uniquement) ──────────────────────
    if not ml_pred and 5 <= days_elapsed < 28:
        avg_daily = current_total / days_elapsed
        projected_28 = avg_daily * 28
        st.info(f"🔮 **Projection :** À ce rythme, vous finirez les 28 jours avec environ **{projected_28:,.0f} streams**.")
        if projected_28 > 10000:
            st.success("🌟 Vous êtes en bonne voie pour le Discover Weekly !")
        elif projected_28 > 1000:
            st.warning("⚠️ Release Radar probable, mais Discover Weekly hors de portée sans boost.")
        else:
            st.error("📉 Trajectoire insuffisante pour les algos majeurs.")

    db.close()
