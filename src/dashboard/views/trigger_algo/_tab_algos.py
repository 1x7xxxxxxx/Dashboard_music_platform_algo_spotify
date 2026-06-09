"""trigger_algo — _show_tab_algos (move-only split)."""
from datetime import timedelta
from plotly.subplots import make_subplots
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.dashboard.utils import ml_widgets
from src.utils.track_matching import canonical_song_sql
from ._common import (
    ELBOW_THRESHOLDS_28D,
    _show_28d_gate,
    _show_discovery_mode_protocol,
    _show_feature_importance,
    _show_phase_strategy,
    _show_pi_gate_section,
    _show_radio_snowball,
    _show_resurrection_radar,
    _show_verdict_banner,
)


def _show_tab_algos(db, track: str, artist_id, date_from, date_to, ml_pred, release_date=None):
    st.caption(
        "📊 **Suivi & action** — le verdict (STOP / OPTIMISER / SCALER), les leviers concrets "
        "pour ouvrir chaque porte algorithmique, ta position sur les courbes PI, et la "
        "trajectoire des 28 premiers jours vs les seuils réels de déclenchement."
    )
    _show_verdict_banner(ml_pred)
    _show_phase_strategy(ml_pred)
    _show_radio_snowball(db, artist_id)
    _show_resurrection_radar(db, artist_id)
    st.divider()
    _show_pi_gate_section(ml_pred)
    _show_feature_importance()
    _show_discovery_mode_protocol()
    st.divider()
    with st.expander("🔮 Simulateur Release Radar (pré-sortie) — planifier une sortie"):
        ml_widgets.render_prerelease_rr_estimator()
    st.divider()
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
            df_pi = db.fetch_df(
                f"SELECT date, popularity FROM track_popularity_history WHERE {canonical_song_sql('track_name')} = %s AND artist_id = %s AND date BETWEEN %s AND %s ORDER BY date",
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
            df_pi = db.fetch_df(
                f"SELECT date, popularity FROM track_popularity_history WHERE {canonical_song_sql('track_name')} = %s AND date BETWEEN %s AND %s ORDER BY date",
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

            if not df_pi.empty:
                df_pi["date"] = pd.to_datetime(df_pi["date"])
                fig.add_trace(go.Scatter(
                    x=df_pi["date"], y=df_pi["popularity"],
                    name="Popularity Index", mode="lines",
                    line=dict(color="#FFFFFF", width=1.5, dash="dot")
                ), secondary_y=True)

            fig.update_layout(
                title=f"Streams & probabilités — {track}",
                hovermode="x unified", height=480,
                legend=dict(orientation="h", y=1.12)
            )
            fig.update_yaxes(title_text="Streams", secondary_y=False)
            fig.update_yaxes(title_text="Proba algo (%) / Popularity Index", secondary_y=True, range=[0, 100])
            st.plotly_chart(fig, width='stretch')
    except Exception as e:
        st.warning(f"Graphique streams/probas indisponible : {e}")

    _show_28d_gate(db, track, artist_id)
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
                f"SELECT date, popularity FROM track_popularity_history WHERE {canonical_song_sql('track_name')} = %s AND artist_id = %s ORDER BY date ASC",
                (track, artist_id)
            )
        else:
            df_full = db.fetch_df(
                "SELECT date, streams FROM s4a_song_timeline WHERE song = %s ORDER BY date ASC",
                (track,)
            )
            df_pop = db.fetch_df(
                f"SELECT date, popularity FROM track_popularity_history WHERE {canonical_song_sql('track_name')} = %s ORDER BY date ASC",
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
            # Trigger thresholds are intentionally NOT drawn as reference lines: they are
            # algo-streams the playlists GENERATE (detection signal), not a target on the
            # song's own cumulative streams. They are described in the caption below instead.
            fig2.update_layout(
                title=f"Trajectoire de '{track}' (28 premiers jours)",
                xaxis_title="Jours depuis la sortie (J+)",
                hovermode="x unified", height=550,
                legend=dict(orientation="h", y=1.12)
            )
            fig2.update_yaxes(title_text="Volume Streams", secondary_y=False)
            fig2.update_yaxes(title_text="Popularité (0-100)", secondary_y=True, range=[0, 100])
            st.plotly_chart(fig2, width='stretch')
            st.caption(
                "Courbe = streams cumulés du titre sur ses 28 premiers jours. "
                "ℹ️ **À propos des seuils de trigger :** quand une playlist algorithmique se "
                "déclenche, elle génère elle-même un volume d'algo-streams (28j) qui démarre "
                "autour de **~130 (RR)**, **~137 (DW)**, **~639 (Radio)** et se stabilise vers "
                "**~417 / ~1 333 / ~8 423** une fois installée. Ce sont des volumes **produits "
                "par les playlists** (signal de détection) — **pas** un objectif de streams à "
                "atteindre soi-même pour les déclencher. C'est pourquoi ils ne sont pas tracés "
                "comme des lignes-cibles sur ta courbe."
            )

            # Linear projection fallback
            if not ml_pred and 5 <= days_elapsed < 28:
                avg_daily = current_total / days_elapsed
                projected_28 = avg_daily * 28
                st.info(f"🔮 **Projection :** À ce rythme → ~**{projected_28:,.0f} streams** en 28j.")
                if projected_28 > ELBOW_THRESHOLDS_28D["DW"]:
                    st.success("🌟 Volume cohérent avec un trigger Discover Weekly amorcé "
                               "(au niveau d'algo-streams qu'une playlist émet à son début).")
                elif projected_28 > ELBOW_THRESHOLDS_28D["RR"]:
                    st.warning("⚠️ Au niveau d'un début de trigger Release Radar ; "
                               "Discover Weekly encore juste.")
                else:
                    st.error("📉 Sous le niveau d'algo-streams d'un trigger qui démarre.")
    except Exception as e:
        st.warning(f"Trajectoire J+28 indisponible : {e}")
