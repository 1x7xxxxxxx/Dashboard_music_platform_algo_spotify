"""Saisie S4A — windowed playlist adds (7d/28d/12m + custom) & Discovery Mode.

Type: Feature
Uses: streamlit, pandas, src.dashboard.utils.view_session
Depends on: s4a_song_timeline (track list)
Persists in: s4a_song_playlist_adds (windowed), s4a_song_discovery_mode,
  s4a_song_nonalgo_streams, s4a_artist_radio_count

Bulk manual-entry grid for S4A signals that have no API. One row per track:
- playlist adds over 7d / 28d / 12m (windowed snapshots, migration 044),
- Discovery Mode opt-in,
- 28-day non-algo (organic) streams (migration 052),
plus a per-artist "# songs in Radio now" counter (migration 052) and a separate
custom-range section (key in the first days after a release). The non-algo streams
and radio count un-impute the last two ml_inference features (were hard-coded 0).
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t

_ARTIST_FILTER = "%1x7xxxxxxx%"
_WINDOWS = [("Playlist 7j", "7d"), ("Playlist 28j", "28d"), ("Playlist 12 mois", "12m")]


def _load_tracks(db, artist_id) -> list[str]:
    if artist_id:
        rows = db.fetch_df(
            """SELECT t.song FROM (SELECT song FROM s4a_song_timeline
                 WHERE song NOT ILIKE %s AND artist_id = %s GROUP BY song) t
               LEFT JOIN tracks tk ON REPLACE(tk.track_name,'?','_') = t.song
                                      AND tk.saas_artist_id = %s
               ORDER BY tk.release_date DESC NULLS LAST, t.song""",
            (_ARTIST_FILTER, artist_id, artist_id))
    else:
        rows = db.fetch_df(
            """SELECT t.song FROM (SELECT song FROM s4a_song_timeline
                 WHERE song NOT ILIKE %s GROUP BY song) t
               LEFT JOIN tracks tk ON REPLACE(tk.track_name,'?','_') = t.song
               ORDER BY tk.release_date DESC NULLS LAST, t.song""",
            (_ARTIST_FILTER,))
    return rows["song"].tolist() if rows is not None and not rows.empty else []


def _latest_windowed(db, artist_id) -> dict:
    """{(song, window): count} latest snapshot per (song, window)."""
    rows = db.fetch_query(
        """SELECT DISTINCT ON (song, time_window) song, time_window, count
           FROM s4a_song_playlist_adds
           WHERE artist_id = %s AND time_window IN ('7d','28d','12m')
           ORDER BY song, time_window, recorded_at DESC""",
        (artist_id,)) if artist_id else []
    return {(r[0], r[1]): int(r[2] or 0) for r in rows} if rows else {}


def _latest_discovery(db, artist_id) -> dict:
    rows = db.fetch_query(
        """SELECT DISTINCT ON (song) song, opted_in FROM s4a_song_discovery_mode
           WHERE artist_id = %s ORDER BY song, recorded_at DESC""",
        (artist_id,)) if artist_id else []
    return {r[0]: bool(r[1]) for r in rows} if rows else {}


def _latest_nonalgo(db, artist_id) -> dict:
    """{song: streams_28d} latest non-algo 28-day stream snapshot per song."""
    rows = db.fetch_query(
        """SELECT DISTINCT ON (song) song, streams_28d FROM s4a_song_nonalgo_streams
           WHERE artist_id = %s ORDER BY song, recorded_at DESC""",
        (artist_id,)) if artist_id else []
    return {r[0]: int(r[1] or 0) for r in rows} if rows else {}


def _latest_radio_count(db, artist_id) -> int:
    """Latest per-artist count of songs currently in Spotify Radio (0 if none)."""
    rows = db.fetch_query(
        """SELECT song_count FROM s4a_artist_radio_count
           WHERE artist_id = %s ORDER BY recorded_at DESC LIMIT 1""",
        (artist_id,)) if artist_id else []
    return int(rows[0][0]) if rows and rows[0][0] is not None else 0


def _render_fixed_grid(db, artist_id, tracks) -> None:
    st.subheader(t("saisie_s4a.fixed_header", "📊 Ajouts en playlist par fenêtre + Discovery Mode"))
    st.caption(t("saisie_s4a.fixed_caption",
                 "Saisissez, par titre, les ajouts en playlist tels qu'affichés dans S4A "
                 "(7 jours / 28 jours / 12 mois) et l'état Discovery Mode. Sauvegarde groupée."))

    # Step-by-step on where to read each value in the Spotify for Artists UI.
    with st.expander(t("saisie_s4a.howto_header",
                       "ℹ️ Où trouver ces valeurs dans Spotify for Artists ?")):
        st.markdown(t(
            "saisie_s4a.howto_nonalgo",
            "**Streams non-algo (28j)** — par titre :\n"
            "Onglet **Musique → Titres → sélectionne un titre → Source de streams**. "
            "Dans la segmentation **« Source de streams »**, coche **toutes les sources "
            "actives** : *Profil artiste et catalogue* · *Playlists et bibliothèque de "
            "l'auditeur* · *File d'attente de l'auditeur*. Active le filtre **28 derniers "
            "jours**, puis reporte ici la valeur affichée dans **« Cette période »**."))
        st.markdown(t(
            "saisie_s4a.howto_radio",
            "**Titres actuellement en Radio** — par artiste :\n"
            "Onglet **Musique → Playlists**, clique sur **« Personnalisée »** sur la "
            "playlist **Radio**, puis compte le nombre de titres."))

    # Per-artist signal: number of songs currently pushed in Spotify Radio.
    radio_now = _latest_radio_count(db, artist_id)
    radio_count = st.number_input(
        t("saisie_s4a.radio_count_label", "📻 Nombre de titres actuellement en Radio Spotify"),
        min_value=0, step=1, value=int(radio_now),
        help=t("saisie_s4a.radio_count_help",
               "Musique → Playlists → « Personnalisée » sur la playlist Radio → "
               "compte les titres. Alimente le ML (HowManySongsDoYouHaveInRadioRightNow)."),
        key=f"radio_count_{artist_id}")

    wins = _latest_windowed(db, artist_id)
    disc = _latest_discovery(db, artist_id)
    nonalgo = _latest_nonalgo(db, artist_id)
    df = pd.DataFrame([{
        "Titre": s,
        "Playlist 7j": wins.get((s, "7d"), 0),
        "Playlist 28j": wins.get((s, "28d"), 0),
        "Playlist 12 mois": wins.get((s, "12m"), 0),
        "Discovery Mode": disc.get(s, False),
        "Streams non-algo (28j)": nonalgo.get(s, 0),
    } for s in tracks])

    edited = st.data_editor(
        df, hide_index=True, width="stretch", num_rows="fixed",
        column_config={
            "Titre": st.column_config.TextColumn(disabled=True),
            "Playlist 7j": st.column_config.NumberColumn(min_value=0, step=1),
            "Playlist 28j": st.column_config.NumberColumn(min_value=0, step=1, help=t("saisie_s4a.help_feeds_ml", "Alimente le ML")),
            "Playlist 12 mois": st.column_config.NumberColumn(min_value=0, step=1),
            "Discovery Mode": st.column_config.CheckboxColumn(),
            "Streams non-algo (28j)": st.column_config.NumberColumn(
                min_value=0, step=1,
                help=t("saisie_s4a.nonalgo_help",
                       "Musique → Titres → un titre → Source de streams : coche toutes les "
                       "sources actives + filtre 28 jours, reporte « Cette période ». "
                       "Hors Discover Weekly / Release Radar / Radio / autoplay. Alimente le ML.")),
        },
        key=f"grid_fixed_{artist_id}",
    )

    if st.button(t("saisie_s4a.save_grid", "💾 Enregistrer la grille"), type="primary"):
        _save_fixed(db, artist_id, edited, int(radio_count))


def _save_fixed(db, artist_id, edited: pd.DataFrame, radio_count: int) -> None:
    today = date.today()
    pa_rows, dm_rows, na_rows = [], [], []
    for _, row in edited.iterrows():
        song = row["Titre"]
        for label, win in _WINDOWS:
            pa_rows.append({"artist_id": artist_id, "song": song, "time_window": win,
                            "recorded_at": today, "count": int(row[label] or 0)})
        dm_rows.append({"artist_id": artist_id, "song": song,
                        "recorded_at": today, "opted_in": bool(row["Discovery Mode"])})
        na_rows.append({"artist_id": artist_id, "song": song, "recorded_at": today,
                        "streams_28d": int(row["Streams non-algo (28j)"] or 0)})
    try:
        db.upsert_many("s4a_song_playlist_adds", pa_rows,
                       ["artist_id", "song", "time_window", "recorded_at"],
                       ["count", "collected_at"])
        db.upsert_many("s4a_song_discovery_mode", dm_rows,
                       ["artist_id", "song", "recorded_at"], ["opted_in", "collected_at"])
        db.upsert_many("s4a_song_nonalgo_streams", na_rows,
                       ["artist_id", "song", "recorded_at"], ["streams_28d", "collected_at"])
        db.upsert_many("s4a_artist_radio_count",
                       [{"artist_id": artist_id, "recorded_at": today,
                         "song_count": int(radio_count)}],
                       ["artist_id", "recorded_at"], ["song_count", "collected_at"])
        st.success(t("saisie_s4a.saved_fixed",
                     "Enregistré : {pa} valeurs playlist + {dm} Discovery Mode + "
                     "{na} streams non-algo + Radio = {radio}.")
                   .format(pa=len(pa_rows), dm=len(dm_rows), na=len(na_rows), radio=int(radio_count)))
        st.rerun()
    except Exception as exc:
        st.error(t("saisie_s4a.error", "Erreur : {exc}").format(exc=exc))


def _render_custom_grid(db, artist_id, tracks) -> None:
    st.subheader(t("saisie_s4a.custom_header", "📅 Plage personnalisée (ex. premiers jours post-release)"))
    today = date.today()
    c1, c2 = st.columns(2)
    start = c1.date_input(t("saisie_s4a.custom_start", "Début"), value=today - timedelta(days=3),
                          format="YYYY-MM-DD", key=f"custom_start_{artist_id}")
    end = c2.date_input(t("saisie_s4a.custom_end", "Fin"), value=today, format="YYYY-MM-DD",
                        key=f"custom_end_{artist_id}")
    if start > end:
        st.warning(t("saisie_s4a.start_before_end", "La date de début doit précéder la date de fin."))
        return

    df = pd.DataFrame([{"Titre": s, "Ajouts playlist": 0} for s in tracks])
    edited = st.data_editor(
        df, hide_index=True, width="stretch", num_rows="fixed",
        column_config={
            "Titre": st.column_config.TextColumn(disabled=True),
            "Ajouts playlist": st.column_config.NumberColumn(min_value=0, step=1),
        },
        key=f"grid_custom_{artist_id}",
    )
    if st.button(t("saisie_s4a.save_custom", "💾 Enregistrer la plage personnalisée"), type="primary"):
        rows = [{"artist_id": artist_id, "song": r["Titre"], "time_window": "custom",
                 "recorded_at": end, "count": int(r["Ajouts playlist"] or 0),
                 "period_start": start, "period_end": end} for _, r in edited.iterrows()]
        try:
            db.upsert_many("s4a_song_playlist_adds", rows,
                           ["artist_id", "song", "time_window", "recorded_at"],
                           ["count", "period_start", "period_end", "collected_at"])
            st.success(t("saisie_s4a.saved_custom", "Plage {start} → {end} enregistrée pour {n} titres.")
                       .format(start=start, end=end, n=len(rows)))
            st.rerun()
        except Exception as exc:
            st.error(t("saisie_s4a.error", "Erreur : {exc}").format(exc=exc))


def show():
    st.title(t("saisie_s4a.title", "📝 Saisie S4A"))
    st.markdown(t("saisie_s4a.intro",
                  "Signaux **Spotify for Artists uniquement** (aucune API) à saisir par titre. "
                  "Alimentent la prédiction ML « 🚀 Road to Algo »."))
    with view_session() as (db, artist_id):
        if not artist_id:
            st.error(t("saisie_s4a.invalid_session", "Session invalide."))
            return
        tracks = _load_tracks(db, artist_id)
        if not tracks:
            st.warning(t("saisie_s4a.no_tracks", "Aucun titre disponible (timeline S4A vide)."))
            return
        _render_fixed_grid(db, artist_id, tracks)
        st.markdown("---")
        _render_custom_grid(db, artist_id, tracks)
