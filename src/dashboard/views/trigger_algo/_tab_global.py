"""trigger_algo — _show_tab_global (move-only split)."""
from datetime import timedelta
import pandas as pd
import streamlit as st
from ._common import (
    _load_scored_tracks,
    _show_heuristic_section,
    _show_ml_section,
)


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
    with st.expander("✏️ Mettre à jour les playlists (saisie manuelle)", expanded=False):
        st.caption("Saisissez le nombre de playlists affiché dans S4A pour ce titre.")
        with st.form(key=f"pl_count_form_{track}_{artist_id}", clear_on_submit=False):
            fc1, fc2 = st.columns([2, 1])
            new_count = fc1.number_input("Nombre de playlists", min_value=0,
                                         value=current_pl_count, step=1)
            entry_date = fc2.date_input("Date de relevé", value=date_to, format="YYYY-MM-DD")
            if st.form_submit_button("Enregistrer", type="primary"):
                try:
                    db.upsert_many(
                        table='s4a_song_playlist_adds',
                        data=[{'artist_id': artist_id, 'song': track,
                               'recorded_at': entry_date, 'count': int(new_count)}],
                        conflict_columns=['artist_id', 'song', 'recorded_at'],
                        update_columns=['count', 'collected_at'],
                    )
                    st.success(f"{int(new_count)} playlist(s) enregistrée(s) au {entry_date}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

    # ── Discovery Mode (saisie manuelle) ─────────────────────────────────────
    # S4A-UI-only signal (no API). Un-impute le feature ML
    # IsThisSongOptedIntoSpotifyDiscoveryMode (sinon imputé à 0).
    st.subheader("🔭 Discovery Mode")
    try:
        dm_row = db.fetch_query(
            "SELECT opted_in, recorded_at FROM s4a_song_discovery_mode "
            "WHERE artist_id = %s AND song = %s "
            "ORDER BY recorded_at DESC LIMIT 1",
            (artist_id, track),
        ) if artist_id else db.fetch_query(
            "SELECT opted_in, recorded_at FROM s4a_song_discovery_mode "
            "WHERE song = %s ORDER BY recorded_at DESC LIMIT 1",
            (track,),
        )
        current_dm = bool(dm_row[0][0]) if dm_row and dm_row[0][0] is not None else False
        dm_recorded = dm_row[0][1] if dm_row else None
    except Exception:
        current_dm = False
        dm_recorded = None

    st.metric(
        "Discovery Mode",
        "Activé" if current_dm else "Désactivé",
        help=f"Dernier relevé : {dm_recorded or '—'}. Visible dans Spotify for Artists "
             "uniquement — à saisir manuellement. Alimente la prédiction ML.",
    )
    if artist_id:
        with st.expander("✏️ Mettre à jour le Discovery Mode (saisie manuelle)", expanded=False):
            with st.form(key=f"dm_form_{track}_{artist_id}", clear_on_submit=False):
                dc1, dc2 = st.columns([2, 1])
                new_dm = dc1.checkbox("Opt-in Discovery Mode pour ce titre", value=current_dm)
                dm_date = dc2.date_input("Date de relevé", value=date_to, format="YYYY-MM-DD")
                if st.form_submit_button("Enregistrer", type="primary"):
                    try:
                        db.upsert_many(
                            table='s4a_song_discovery_mode',
                            data=[{'artist_id': artist_id, 'song': track,
                                   'recorded_at': dm_date, 'opted_in': bool(new_dm)}],
                            conflict_columns=['artist_id', 'song', 'recorded_at'],
                            update_columns=['opted_in', 'collected_at'],
                        )
                        st.success(
                            f"Discovery Mode {'activé' if new_dm else 'désactivé'} au {dm_date}.")
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
