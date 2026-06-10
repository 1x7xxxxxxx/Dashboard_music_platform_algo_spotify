"""trigger_algo lifecycle — move-only split of _common."""
from datetime import date
from src.dashboard.utils.i18n import t
import plotly.graph_objects as go
import streamlit as st


_LIFECYCLE_AGE_BINS = [
    ("0-5", 1, 0, 5), ("5-10", 2, 5, 10), ("10-25", 3, 10, 25),
    ("25-50", 4, 25, 50), ("50-100", 5, 50, 100), ("100+", 6, 100, 10**9),
]


_LIFECYCLE_PALETTE = {"DW": "rgb(0,200,220)", "RR": "rgb(255,165,0)", "RADIO": "rgb(29,185,84)"}


_LIFECYCLE_LABELS = {"DW": "💎 Discover Weekly", "RR": "📡 Release Radar", "RADIO": "📻 Radio"}


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
