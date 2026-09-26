"""trigger_algo — _show_tab_model (move-only split)."""
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import secondary_analyses
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _show_tab_model(db, track: str, artist_id):
    st.caption(t(
        "trigger_algo.model.caption",
        "📈 **Sous le capot** — la fiabilité technique du modèle ML : précision de "
        "classification par algo, et volume prévu à côté des streams observés. Pour juger à "
        "quel point tu peux faire confiance aux probabilités affichées dans les autres onglets."
    ))
    for _algo in ak.populated_algos():
        if _algo in ak.ALGO_MODEL_METRICS:
            ml_widgets.render_classification_scorecard(_algo, compact=True)
    st.markdown("---")
    st.subheader(t("trigger_algo.model.actual_vs_pred",
                   "📊 Volume prévu par le modèle et streams observés"))
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
            st.info(t("trigger_algo.model.insufficient_history",
                      "Historique insuffisant (minimum 2 prédictions avec streams_7d renseigné)."))
            return

        # Only `actual` is guaranteed (SQL filters streams_7d IS NOT NULL). Each algo
        # subplot drops NaN on its OWN forecast column — do NOT drop on predicted_dw
        # globally: the DW volume regressor is frozen by design (R²<0), so predicted_dw
        # is always NULL and a global dropna would wipe RR/Radio too.
        df_hist = df_hist.dropna(subset=["actual"])
        df_hist["prediction_date"] = pd.to_datetime(df_hist["prediction_date"])

        for _col, _algo in zip(st.columns(len(_SCATTER_ALGOS)), _SCATTER_ALGOS):
            with _col:
                _show_volume_scatter(df_hist, _algo)

        # Diagnostic du MODÈLE : ces résidus affinent la compréhension, ils ne
        # décident rien pour l'artiste — la définition littérale de
        # `secondary_analyses()`. Cet onglet portait 4 figures sur les ~35 de la
        # vue, la plus dense du tableau de bord, et R51 demandait d'appliquer un
        # motif DÉJÀ écrit (2026-08-12, pour la remarque « réduire le nombre de
        # graphs ») aux cinq vues denses. Quatre l'avaient ; celle-ci pas.
        # Rien n'est supprimé : tout reste à un clic.
        with secondary_analyses(t("trigger_algo.model.residuals_expander",
                                  "📉 Diagnostic du modèle — résidus (facultatif)")):
            st.markdown("---")
            st.subheader(t("trigger_algo.model.residuals_header",
                           "📉 Résidus dans le temps (Actuel − Forecast DW)"))
            # Residuals are the DW forecast by another name: same gate as the scatter.
            df_res = (df_hist.dropna(subset=["predicted_dw"]).copy()
                      if ak.volume_forecast_reliable("DW") else df_hist.iloc[0:0])
            if df_res.empty:
                st.info(t("trigger_algo.model.no_residuals",
                          "Résidus DW indisponibles — le volume DW n'est pas prédit (régresseur "
                          "gelé par design). Rien d'anormal pour ce titre."))
            else:
                df_res["residual"] = df_res["actual"].astype(float) - df_res["predicted_dw"].astype(float)
                colors = ["#1DB954" if r >= 0 else "#FF6B6B" for r in df_res["residual"]]

                fig_res = go.Figure()
                fig_res.add_trace(go.Bar(
                    x=df_res["prediction_date"], y=df_res["residual"],
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

                mean_res = df_res["residual"].mean()
                std_res = df_res["residual"].std()
                st.caption(t("trigger_algo.model.bias_caption",
                             "Biais moyen : {mean:,.0f} streams | Écart-type : {std:,.0f} streams")
                           .format(mean=mean_res, std=std_res))
                if len(df_res) >= 3 and abs(mean_res) > std_res:
                    st.warning(t("trigger_algo.model.systematic_bias",
                                 "Biais systématique détecté — le modèle sur- ou sous-prédit "
                                 "de façon consistante pour ce titre."))

    except Exception as e:
        st.warning(t("trigger_algo.model.chart_unavailable",
                     "Graphique Actual vs Predicted indisponible : {err}").format(err=e))


# One scatter per algo, in display order. The column each one reads is the
# regressor's volume forecast, which `machine_learning/train.py:122-128` trains on
# an ALGO-SOURCED, 28-DAY target (the `_7d` in the column name is a known misnomer).
_SCATTER_ALGOS = ("DW", "RR", "RADIO")
_FORECAST_COL = {"DW": "predicted_dw", "RR": "predicted_rr", "RADIO": "predicted_radio"}
_ALGO_LABEL = {"DW": "Discover Weekly", "RR": "Release Radar", "RADIO": "Radio"}
_ALGO_COLOR = {"DW": "#1DB954", "RR": "#4ECDC4", "RADIO": "#FFA500"}


def _show_volume_scatter(df_hist: pd.DataFrame, algo: str) -> None:
    """Draw one algo's volume forecast next to the observed streams, or say why not.

    Two defects lived here until 2026-09-26, both read in this file:

    1. A forecast the product suppresses was drawn anyway. `volume_forecast_reliable`
       is the single source that decides whether a volume regressor may be shown
       (`_verdict.py` and `revenue_forecast.py` honour it). This tab plotted the RR
       forecast unconditionally and only used the gate for a caption. The gate now
       decides whether the chart EXISTS, for every algo, never a literal `"RR"`.
    2. Two different quantities on one pair of axes. x is an algo-sourced 28-day
       volume forecast; y (`streams_7d`) is ALL-source 7-day streams. Both axes were
       labelled "streams 7j" and a y=x "Prédiction parfaite" line invited the reader
       to judge the model by a distance that has no meaning. No algo-sourced actual
       exists in the schema, so the y=x line is gone and the axes say what they carry.
    Guard: tests/test_a_suppressed_forecast_is_never_drawn.py
    """
    label = _ALGO_LABEL[algo]
    st.write({
        "DW": lambda: t("trigger_algo.model.dw_forecast", "**DW forecast**"),
        "RR": lambda: t("trigger_algo.model.rr_forecast", "**RR forecast**"),
        "RADIO": lambda: t("trigger_algo.model.radio_forecast", "**Radio forecast**"),
    }[algo]())
    if not ak.volume_forecast_reliable(algo):
        st.info(ml_widgets.suppressed_note_text(algo) or t(
            "trigger_algo.model.volume_suppressed",
            "Volume non prédit : le régresseur de volume n'est pas assez fiable pour "
            "être montré. Fie-toi à la probabilité, pas au volume."))
        return
    col = _FORECAST_COL[algo]
    df_algo = df_hist.dropna(subset=[col]) if col in df_hist.columns else df_hist.iloc[0:0]
    if df_algo.empty:
        st.info(t("trigger_algo.model.no_volume_pred",
                  "Pas de prévision de volume {label} pour ce titre.").format(label=label))
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_algo[col].astype(float),
        y=df_algo["actual"].astype(float),
        mode="markers",
        marker=dict(color=_ALGO_COLOR[algo], size=8),
        name=label,
        text=df_algo["prediction_date"].dt.strftime("%Y-%m-%d"),
        hovertemplate=("Date: %{text}<br>Plancher prédit: %{x:,}"
                       "<br>Streams 7j (toutes sources): %{y:,}"),
    ))
    fig.update_layout(
        xaxis_title=t("trigger_algo.model.x_floor",
                      "Plancher {label} prédit (streams issus de {label}, 28 j)"
                      ).format(label=label),
        yaxis_title=t("trigger_algo.model.y_all_streams",
                      "Streams observés, toutes sources (7 j)"),
        height=340, showlegend=False,
    )
    st.plotly_chart(fig, width='stretch')
    st.caption(t("trigger_algo.model.axes_differ",
                 "Les deux axes ne mesurent pas la même chose : le modèle prédit un plancher "
                 "de streams venus de {label} sur 28 jours, l'axe vertical compte tous les "
                 "streams du titre sur 7 jours. Aucune donnée ne mesure les streams venus "
                 "de {label} seuls : cette vue montre une tendance, pas l'erreur du modèle."
                 ).format(label=label))
