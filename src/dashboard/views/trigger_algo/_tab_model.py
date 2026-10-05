"""trigger_algo — _show_tab_model (move-only split)."""
from src.dashboard.utils import algo_knowledge as ak, charts
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import ALGO_COLORS
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.utils.algo_order import ALGO_ORDER


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
    _show_error_by_prediction_week(db, artist_id)


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
_SCATTER_ALGOS = ALGO_ORDER
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


# R297 (R293, the owner's call on 2026-09-28; corpus: Crowe et al., p. 322). Fiche 51 sets
# the LATEST prediction of each title against its reading — one point, never a trend.
# Here every prediction made before the reading is set against that same reading, per
# WEEK the prediction was made: a flat line says the model did not change its mind from
# week to week; a line falling towards the reading says it learned. While S4A carries one
# reading per title, every week is judged against the same truth — the caption says so.
_WEEKLY_SQL = """
    SELECT p.prediction_date, o.song, o.recorded_at,
           o.dw_streams, o.rr_streams, o.radio_streams,
           p.dw_streams_forecast_7d AS predicted_dw, p.rr_streams_forecast_7d AS predicted_rr,
           p.radio_streams_forecast_7d AS predicted_radio
    FROM (SELECT DISTINCT ON (song) song, artist_id, recorded_at,
                 dw_streams, rr_streams, radio_streams
          FROM s4a_song_algo_outcomes
          WHERE artist_id = %s AND time_window = '28d' AND song NOT ILIKE '%%1x7xxxxxxx%%'
          ORDER BY song, recorded_at DESC) o
    JOIN ml_song_predictions p ON p.song = o.song AND p.artist_id = o.artist_id
     AND p.prediction_date <= o.recorded_at"""


def error_by_prediction_week(rows: pd.DataFrame, algo: str) -> pd.DataFrame:
    """[week, error, titles] — the median absolute gap between the forecasts made that week
    and the S4A reading, for one algorithm. Pure; empty when nothing can be compared."""
    pred, act = _FORECAST_COL[algo], _ACTUAL_COL[algo]
    d = rows.dropna(subset=[pred, act, "prediction_date"])
    if d.empty:
        return pd.DataFrame(columns=["week", "error", "titles"])
    d = d.assign(week=pd.to_datetime(d["prediction_date"]).dt.to_period("W").dt.start_time,
                 gap=(d[pred].astype(float) - d[act].astype(float)).abs())
    return (d.groupby("week").agg(error=("gap", "median"), titles=("song", "nunique"))
            .reset_index().sort_values("week"))


def _show_error_by_prediction_week(db, artist_id) -> None:
    """The model's error per week of prediction, for every algorithm whose volume is shown."""
    shown = [a for a in _SCATTER_ALGOS if ak.volume_forecast_reliable(a)]
    if not shown:
        return
    st.subheader(t("trigger_algo.model.weekly_title",
                   "📉 L'erreur du modèle, semaine de prédiction par semaine"))
    try:
        rows = db.fetch_df(_WEEKLY_SQL, (artist_id,))
    except Exception as e:                                           # noqa: BLE001
        st.warning(t("trigger_algo.model.chart_unavailable",
                     "Graphique indisponible : {err}").format(err=e))
        return
    series = {a: error_by_prediction_week(rows, a) for a in shown} if rows is not None else {}
    series = {a: s for a, s in series.items() if not s.empty}
    if not series:
        st.info(t("trigger_algo.model.weekly_empty",
                  "Aucune prédiction faite avant un relevé S4A : rien à comparer."))
        return
    # A week without any prediction is a HOLE, not a straight line across it.
    series = {a: s.set_index("week").reindex(pd.date_range(
        s["week"].min(), s["week"].max(), freq="7D")).rename_axis("week").reset_index()
        for a, s in series.items()}
    fig = go.Figure([go.Scatter(
        x=s["week"], y=s["error"], mode="lines+markers", name=_ALGO_LABEL[a],
        connectgaps=False,
        line=dict(color=_ALGO_COLOR[a], width=2),
        customdata=s["titles"],
        hovertemplate="%{x|%Y-%m-%d} : %{y:.0f} streams d'écart (%{customdata} titres)"
                      "<extra></extra>") for a, s in series.items()])
    fig.update_layout(height=340, showlegend=True, yaxis_title=t(
        "trigger_algo.model.weekly_y", "Écart prévu / constaté (streams)"),
        xaxis_title=t("trigger_algo.model.weekly_x", "Semaine où la prédiction a été faite"),
        legend=dict(orientation="h", y=-0.35))
    fig.update_yaxes(rangemode="tozero")
    charts.plotly_chart(fig, width='stretch')
    readings = pd.to_datetime(rows["recorded_at"]).dt.date.nunique()
    weeks = max(int(s["error"].notna().sum()) for s in series.values())
    st.caption(t(
        "trigger_algo.model.weekly_caption",
        "{weeks} semaine(s) de prédictions jugées contre {readings} relevé(s) S4A. Une ligne "
        "plate : le modèle n'a pas changé d'avis d'une semaine à l'autre ; une ligne qui "
        "descend : il se rapproche du constat. Avec un seul relevé, chaque semaine est "
        "jugée contre la même vérité — la série s'étoffera à chaque saisie S4A."
    ).format(weeks=weeks, readings=readings))
