"""trigger_algo — _show_tab_model (move-only split)."""
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils import ml_widgets
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


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
