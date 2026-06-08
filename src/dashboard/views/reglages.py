"""Manual-entry settings page: S4A-UI-only signals not exposed by any API.

Type: Feature
Uses: streamlit, src.dashboard.utils.view_session
Triggers: user manual entry of playlist adds + Discovery Mode opt-in
Depends on: s4a_song_timeline (track list), tracks (release ordering)
Persists in: s4a_song_playlist_adds, s4a_song_discovery_mode
"""
import streamlit as st

from src.dashboard.utils import view_session


def _load_tracks(db, artist_id):
    """Track names for the tenant, ordered by release_date DESC (same as Road to Algo)."""
    if artist_id:
        return db.fetch_df(
            """SELECT t.song
               FROM (SELECT song FROM s4a_song_timeline
                     WHERE song NOT ILIKE %s AND artist_id = %s GROUP BY song) t
               LEFT JOIN tracks tk ON REPLACE(tk.track_name, '?', '_') = t.song
                                      AND tk.saas_artist_id = %s
               ORDER BY tk.release_date DESC NULLS LAST, t.song""",
            ("%1x7xxxxxxx%", artist_id, artist_id),
        )["song"].tolist()
    return db.fetch_df(
        """SELECT t.song
           FROM (SELECT song FROM s4a_song_timeline
                 WHERE song NOT ILIKE %s GROUP BY song) t
           LEFT JOIN tracks tk ON REPLACE(tk.track_name, '?', '_') = t.song
           ORDER BY tk.release_date DESC NULLS LAST, t.song""",
        ("%1x7xxxxxxx%",),
    )["song"].tolist()


def _render_playlist_adds(db, track, artist_id):
    st.subheader("🎧 Ajouts en playlist")
    st.caption("Donnée visible dans l'UI Spotify for Artists uniquement (aucune API). "
               "Saisie cumulative datée par relevé.")
    try:
        row = db.fetch_query(
            "SELECT count, recorded_at FROM s4a_song_playlist_adds "
            "WHERE artist_id = %s AND song = %s ORDER BY recorded_at DESC LIMIT 1",
            (artist_id, track),
        ) if artist_id else db.fetch_query(
            "SELECT count, recorded_at FROM s4a_song_playlist_adds "
            "WHERE song = %s ORDER BY recorded_at DESC LIMIT 1",
            (track,),
        )
        current = int(row[0][0]) if row and row[0][0] is not None else 0
        last = row[0][1] if row else None
    except Exception:
        current, last = 0, None

    st.metric("Playlists ajoutées (dernier relevé)", current,
              help=f"Dernier enregistrement : {last or '—'}.")
    with st.form(key=f"pl_count_form_{track}_{artist_id}", clear_on_submit=False):
        fc1, fc2 = st.columns([2, 1])
        new_count = fc1.number_input("Nombre de playlists", min_value=0, value=current, step=1)
        entry_date = fc2.date_input("Date de relevé", format="YYYY-MM-DD")
        if st.form_submit_button("Enregistrer", type="primary"):
            try:
                db.upsert_many(
                    table='s4a_song_playlist_adds',
                    data=[{
                        'artist_id':   artist_id,
                        'song':        track,
                        'recorded_at': entry_date,
                        'count':       int(new_count),
                    }],
                    conflict_columns=['artist_id', 'song', 'recorded_at'],
                    update_columns=['count', 'collected_at'],
                )
                st.success(f"{int(new_count)} playlist(s) enregistrée(s) au {entry_date}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")


def _render_discovery_mode(db, track, artist_id):
    st.subheader("🔭 Discovery Mode")
    st.caption("Visible dans Spotify for Artists uniquement — alimente la prédiction ML "
               "(sinon imputé à 0, ce qui fausse DW/Radio).")
    try:
        row = db.fetch_query(
            "SELECT opted_in, recorded_at FROM s4a_song_discovery_mode "
            "WHERE artist_id = %s AND song = %s ORDER BY recorded_at DESC LIMIT 1",
            (artist_id, track),
        ) if artist_id else db.fetch_query(
            "SELECT opted_in, recorded_at FROM s4a_song_discovery_mode "
            "WHERE song = %s ORDER BY recorded_at DESC LIMIT 1",
            (track,),
        )
        current = bool(row[0][0]) if row and row[0][0] is not None else False
        last = row[0][1] if row else None
    except Exception:
        current, last = False, None

    st.metric("Discovery Mode (dernier relevé)", "Activé" if current else "Désactivé",
              help=f"Dernier relevé : {last or '—'}.")

    if not artist_id:
        st.info("La saisie Discovery Mode est réservée aux comptes artistes (tenant requis).")
        return

    with st.form(key=f"dm_form_{track}_{artist_id}", clear_on_submit=False):
        dc1, dc2 = st.columns([2, 1])
        new_dm = dc1.checkbox("Opt-in Discovery Mode pour cette track", value=current)
        dm_date = dc2.date_input("Date de relevé", format="YYYY-MM-DD")
        if st.form_submit_button("Enregistrer", type="primary"):
            try:
                db.upsert_many(
                    table='s4a_song_discovery_mode',
                    data=[{
                        'artist_id':   artist_id,
                        'song':        track,
                        'recorded_at': dm_date,
                        'opted_in':    bool(new_dm),
                    }],
                    conflict_columns=['artist_id', 'song', 'recorded_at'],
                    update_columns=['opted_in', 'collected_at'],
                )
                st.success(f"Discovery Mode {'activé' if new_dm else 'désactivé'} au {dm_date}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")


def show():
    st.title("⚙️ Réglages — Saisie manuelle")
    st.markdown(
        "Données **Spotify for Artists uniquement** (aucune API ne les expose) : "
        "à saisir ici par titre. Elles alimentent la « 🚀 Road to Algo (ML) »."
    )

    with view_session() as (db, artist_id):
        try:
            tracks = _load_tracks(db, artist_id)
        except Exception:
            tracks = []

        if not tracks:
            st.warning("Aucun titre disponible (timeline S4A vide).")
            return

        track = st.selectbox("🎵 Titre", tracks)
        st.markdown("---")
        _render_playlist_adds(db, track, artist_id)
        st.markdown("---")
        _render_discovery_mode(db, track, artist_id)
