"""trigger_algo — _show_tab_model (move-only split)."""
from src.dashboard.utils import algo_knowledge as ak, charts
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import ALGO_COLORS
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
    st.subheader(t("trigger_algo.model.forecast_vs_recorded",
                   "📊 Volume prévu par le modèle et streams d'algorithme constatés"))
    try:
        df = db.fetch_df(_RECORDED_SQL, (artist_id,))
    except Exception as e:                                           # noqa: BLE001
        st.warning(t("trigger_algo.model.chart_unavailable",
                     "Graphique indisponible : {err}").format(err=e))
        return
    if df is None or df.empty:
        st.info(t("trigger_algo.model.no_recorded",
                  "Aucun relevé S4A des streams DW / RR / Radio (📝 Saisie S4A, fenêtre "
                  "28 jours) pour cet artiste : rien à confronter au modèle."))
        return
    for _col, _algo in zip(st.columns(len(_SCATTER_ALGOS)), _SCATTER_ALGOS):
        with _col:
            _show_volume_vs_recorded(df, _algo)


# R247 (fiche 51, owner : « je ne comprends pas la valeur ajoutée : refais »). The old
# scatter set an algo-sourced 28-day forecast against ALL-source 7-day streams and said
# itself it measured nothing. The S4A entry now records the streams EACH algorithm
# brought over 28 days: the same quantity as the forecast. Per title, the latest
# prediction made before the reading is set against that reading.
_RECORDED_SQL = """
    SELECT o.song, o.dw_streams, o.rr_streams, o.radio_streams,
           p.dw_streams_forecast_7d AS predicted_dw, p.rr_streams_forecast_7d AS predicted_rr,
           p.radio_streams_forecast_7d AS predicted_radio
    FROM (SELECT DISTINCT ON (song) song, artist_id, recorded_at,
                 dw_streams, rr_streams, radio_streams
          FROM s4a_song_algo_outcomes
          WHERE artist_id = %s AND time_window = '28d' AND song NOT ILIKE '%%1x7xxxxxxx%%'
          ORDER BY song, recorded_at DESC) o
    JOIN LATERAL (SELECT p.dw_streams_forecast_7d, p.rr_streams_forecast_7d,
                         p.radio_streams_forecast_7d FROM ml_song_predictions p
                  WHERE p.song = o.song AND p.artist_id = o.artist_id
                    AND p.prediction_date <= o.recorded_at
                  ORDER BY p.prediction_date DESC LIMIT 1) p ON TRUE
    ORDER BY o.song"""


# One scatter per algo, in display order. The column each one reads is the
# regressor's volume forecast, which `machine_learning/train.py:122-128` trains on
# an ALGO-SOURCED, 28-DAY target (the `_7d` in the column name is a known misnomer).
_SCATTER_ALGOS = ("DW", "RR", "RADIO")
_FORECAST_COL = {"DW": "predicted_dw", "RR": "predicted_rr", "RADIO": "predicted_radio"}
_ALGO_LABEL = {"DW": "Discover Weekly", "RR": "Release Radar", "RADIO": "Radio"}
_ALGO_COLOR = ALGO_COLORS   # R260 — the one algorithm palette


_ACTUAL_COL = {"DW": "dw_streams", "RR": "rr_streams", "RADIO": "radio_streams"}


def volume_verdict(predicted, recorded) -> str:
    """How the forecast compares with what S4A recorded, in one word. Pure."""
    import statistics
    p, r = statistics.median(predicted), statistics.median(recorded)
    if r < 0.5 * p:
        return "over"
    if r > 2 * p:
        return "under"
    return "close"


def _show_volume_vs_recorded(df: pd.DataFrame, algo: str) -> None:
    """One algorithm: per title, the model's 28-day volume next to what S4A recorded.

    The gate (`volume_forecast_reliable`) decides whether the forecast EXISTS on the page
    — a suppressed regressor is never drawn (tests/test_a_suppressed_forecast_is_never_drawn.py)."""
    label = _ALGO_LABEL[algo]
    st.write(f"**{label}**")
    if not ak.volume_forecast_reliable(algo):
        st.info(ml_widgets.suppressed_note_text(algo) or t(
            "trigger_algo.model.volume_suppressed",
            "Volume non prédit : le régresseur de volume n'est pas assez fiable pour "
            "être montré. Fie-toi à la probabilité, pas au volume."))
        return
    d = df.dropna(subset=[_FORECAST_COL[algo], _ACTUAL_COL[algo]])
    if d.empty:
        st.info(t("trigger_algo.model.no_volume_pred",
                  "Pas de prévision de volume {label} pour ces titres.").format(label=label))
        return
    from src.dashboard.utils.labels import unique_short_labels
    names = unique_short_labels(d["song"], 18)
    pred, rec = d[_FORECAST_COL[algo]].astype(float), d[_ACTUAL_COL[algo]].astype(float)
    fig = go.Figure([
        go.Bar(x=names, y=list(pred), name=t("trigger_algo.model.bar_predicted", "Prévu"),
               marker_color=_ALGO_COLOR[algo], opacity=0.45),
        # A recorded 0 is a MEASURE, and the finding: written, since a zero bar has no height.
        go.Bar(x=names, y=list(rec), name=t("trigger_algo.model.bar_recorded", "Constaté (S4A)"),
               marker_color=_ALGO_COLOR[algo], text=[f"{v:.0f}" for v in rec],
               textposition="outside", cliponaxis=False)])
    fig.update_layout(barmode="group", height=340,
                      yaxis_title=t("trigger_algo.model.y_algo_streams",
                                    "Streams venus de {label}, 28 j").format(label=label),
                      legend=dict(orientation="h", y=-0.35))
    charts.plotly_chart(fig, width='stretch')
    st.caption({
        "over": t("trigger_algo.model.verdict_over",
                  "**Le modèle surestime** : il prévoit {p:.0f} streams (médiane), S4A en a "
                  "constaté {r:.0f} sur {n} titres. Ne montre pas ce volume comme une promesse."),
        "under": t("trigger_algo.model.verdict_under",
                   "**Le modèle sous-estime** : {p:.0f} prévus (médiane), {r:.0f} constatés "
                   "sur {n} titres — un plancher prudent, pas une prévision."),
        "close": t("trigger_algo.model.verdict_close",
                   "**Même ordre de grandeur** : {p:.0f} prévus (médiane), {r:.0f} constatés "
                   "sur {n} titres — le volume peut être montré."),
    }[volume_verdict(pred, rec)].format(p=pred.median(), r=rec.median(), n=len(d)))
