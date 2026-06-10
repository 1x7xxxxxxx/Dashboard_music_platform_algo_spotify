"""trigger_algo — _show_tab_global (move-only split)."""
from datetime import timedelta
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.dashboard.utils.i18n import t
from ._common import (
    _load_scored_tracks,
    _show_heuristic_section,
    _show_ml_section,
)


def _show_tab_global(db, track: str, artist_id, date_from, date_to, ml_pred, release_date=None):
    st.caption(t(
        "trigger_algo.global.caption",
        "🎯 **Vue d'ensemble** — les chiffres clés du titre sur la période, l'évolution de "
        "ses probabilités de trigger, et son rang /20 dans ton catalogue. Commence ici."
    ))
    st.subheader(t("trigger_algo.global.metrics_header", "📊 Métriques sur la période sélectionnée"))

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

    # Playlist adds — latest 28d windowed snapshot (migration 044). Entry is done
    # in bulk on the dedicated "📝 Saisie S4A" page.
    try:
        _parow = db.fetch_query(
            "SELECT count FROM s4a_song_playlist_adds "
            "WHERE artist_id = %s AND song = %s AND time_window = '28d' "
            "ORDER BY recorded_at DESC LIMIT 1",
            (artist_id, track),
        ) if artist_id else None
        playlist_adds = int(_parow[0][0]) if _parow and _parow[0][0] is not None else 0
    except Exception:
        playlist_adds = 0

    _tw_label = "28j" if _tw == '28d' else "12m"
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("trigger_algo.global.listeners_metric", "Listeners ({win})").format(win=_tw_label),
                f"{int(listeners or 0):,}" if listeners is not None else "—",
                help=t("trigger_algo.global.listeners_help",
                       "Snapshot {win} depuis s4a_songs_global (source : S4A export)").format(win=_tw_label))
    col2.metric(t("trigger_algo.global.streams_metric", "Streams titre ({win})").format(win=_tw_label),
                f"{int(streams or 0):,}" if streams is not None else "—")
    col3.metric(t("trigger_algo.global.saves_metric", "Saves ({win})").format(win=_tw_label),
                f"{int(saves or 0):,}" if saves is not None else "—",
                help=t("trigger_algo.global.saves_help",
                       "Snapshot {win} depuis s4a_songs_global").format(win=_tw_label))
    col4.metric(t("trigger_algo.global.playlist_adds_metric", "Playlist adds (28j)"),
                f"{int(playlist_adds):,}",
                help=t("trigger_algo.global.playlist_adds_help",
                       "Snapshot 28j — saisie dans « 📝 Saisie S4A » (section Données)"))

    st.markdown("---")

    # Trigger-probability trend — the selected track's 3 algo probabilities over
    # the selected period. The dashed 50 % line is the decision threshold.
    st.subheader(t("trigger_algo.global.trigger_trend_header",
                   "🎚️ Évolution du taux de trigger (titre sélectionné)"))
    st.caption(t(
        "trigger_algo.global.trigger_trend_caption",
        "Probabilité de déclenchement DW / RR / Radio du titre dans le temps. "
        "La ligne pointillée à 50 % marque le seuil de déclenchement décisionnel."
    ))
    try:
        if artist_id:
            df_trig = db.fetch_df(
                """SELECT prediction_date, dw_probability, rr_probability, radio_probability
                   FROM ml_song_predictions
                   WHERE song = %s AND artist_id = %s AND prediction_date BETWEEN %s AND %s
                   ORDER BY prediction_date""",
                (track, artist_id, date_from, date_to),
            )
        else:
            df_trig = db.fetch_df(
                """SELECT prediction_date, dw_probability, rr_probability, radio_probability
                   FROM ml_song_predictions
                   WHERE song = %s AND prediction_date BETWEEN %s AND %s
                   ORDER BY prediction_date""",
                (track, date_from, date_to),
            )
        if df_trig.empty:
            st.info(t("trigger_algo.global.no_ml_history",
                      "Aucun historique de probabilités ML sur cette période."))
        else:
            df_trig["prediction_date"] = pd.to_datetime(df_trig["prediction_date"])
            fig_trig = go.Figure()
            for col, name, color in [
                ("dw_probability", "Discover Weekly", "#FF6B6B"),
                ("rr_probability", "Release Radar", "#4ECDC4"),
                ("radio_probability", "Radio", "#FFE66D"),
            ]:
                fig_trig.add_trace(go.Scatter(
                    x=df_trig["prediction_date"], y=df_trig[col] * 100,
                    name=name, mode="lines+markers", line=dict(color=color, width=2)
                ))
            fig_trig.add_hline(
                y=50, line_dash="dash", line_color="#888888",
                annotation_text=t("trigger_algo.global.threshold_50", "Seuil trigger 50 %")
            )
            fig_trig.update_layout(
                hovermode="x unified", height=380,
                legend=dict(orientation="h", y=1.15),
                xaxis=dict(title=t("trigger_algo.global.axis_pred_date", "Date de prédiction")),
                yaxis=dict(title=t("trigger_algo.global.axis_trigger_proba",
                                   "Probabilité de trigger (%)"), range=[0, 100])
            )
            st.plotly_chart(fig_trig, width='stretch')
    except Exception as e:
        st.warning(t("trigger_algo.global.trigger_curve_unavailable",
                     "Courbe taux de trigger indisponible : {err}").format(err=e))

    st.markdown("---")

    # Note: les relevés « Ajouts en playlist » et « Discovery Mode » se saisissent
    # et se consultent dans la page « 📝 Saisie S4A » (section Données). On ne les
    # ré-affiche plus ici pour éviter la redondance ; ils alimentent la prédiction
    # ML et restent visibles dans le KPI compact « Playlist adds » ci-dessus.

    # Score /20 benchmark
    st.subheader(t("trigger_algo.global.score20_header", "🏆 Score /20 — Benchmark toutes les tracks"))
    st.caption(t(
        "trigger_algo.global.score20_caption",
        "⚖️ Score **relatif** (classement, pas une proba) : "
        "`0.35·DW + 0.35·RR + 0.20·Radio + 0.10·velocity`, puis étiré en **min-max** sur "
        "le catalogue → le **meilleur titre = 20.0, le pire = 0.0**, les autres répartis "
        "entre les deux. C'est un classement interne : 20.0 ne veut PAS dire « 100 % de "
        "chance de trigger », et 0.0 ne veut PAS dire « aucune chance » (juste dernier du "
        "catalogue). **`Streams 28j` n'entre pas dans le calcul** (colonne de contexte). "
        "Quand les probas DW/RR/Radio sont très proches d'un titre à l'autre, c'est la "
        "**velocity** (momentum récent, 10 % du poids) qui départage. Pour la probabilité "
        "**absolue** de déclenchement, lis les colonnes DW % / RR % / Radio % (sorties "
        "calibrées du modèle), pas le score."
    ))
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
                .format({"Score /20": "{:.1f}"}, na_rep="—")
                .applymap(_color_score, subset=["Score /20"])
                .apply(_highlight_selected, axis=1)
            )
            st.dataframe(styled, hide_index=True, width='stretch')
        else:
            st.info(t("trigger_algo.global.no_benchmark_pred",
                      "Aucune prédiction ML disponible pour le benchmark."))
    except Exception as e:
        st.warning(t("trigger_algo.global.benchmark_unavailable",
                     "Score benchmark indisponible : {err}").format(err=e))

    st.markdown("---")

    # J+28 quick stats + probability bars
    st.subheader(t("trigger_algo.global.objectives_header", "🎯 Objectifs Algorithmiques (J+28)"))
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
            c1.metric(t("trigger_algo.global.days_elapsed_metric", "Jours écoulés (J+28)"),
                      f"{days_elapsed}/28",
                      delta=t("trigger_algo.global.days_remaining", "{n} restants")
                      .format(n=max(0, 28 - days_elapsed)), delta_color="inverse")
            c2.metric(t("trigger_algo.global.cumul_streams_metric", "Streams cumulés J+28"),
                      f"{current_total:,.0f}")
        else:
            current_total, days_elapsed = 0, 0
    except Exception:
        current_total, days_elapsed = 0, 0

    if ml_pred:
        _show_ml_section(ml_pred)
    else:
        _show_heuristic_section(current_total, 0)
