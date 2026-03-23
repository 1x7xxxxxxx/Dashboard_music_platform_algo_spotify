"""Page Export CSV global — ZIP téléchargeable avec toutes les données artiste."""
import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.csv_exporter import export_all, table_names as _all_table_names


def _get_artists_list(db) -> list[dict]:
    df = db.fetch_df("SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id")
    return df.to_dict("records")


def show():
    st.title("⬇️ Export CSV — Données artiste")
    st.caption(
        "Téléchargez toutes vos données sous forme d'un fichier ZIP "
        "(un CSV par table). Vos données uniquement — filtrées par artiste."
    )
    st.markdown("---")

    db = get_db_connection()
    if db is None:
        return

    try:
        admin = is_admin()

        # ── Sélection artiste ─────────────────────────────────────────────
        if admin:
            artists = _get_artists_list(db)
            if not artists:
                st.warning("Aucun artiste actif en base.")
                return
            artist_options = {a["name"]: a["id"] for a in artists}
            col1, _ = st.columns([2, 4])
            with col1:
                selected_name = st.selectbox("👤 Artiste à exporter", list(artist_options.keys()))
            export_artist_id = artist_options[selected_name]
            export_artist_name = selected_name
        else:
            export_artist_id = get_artist_id()
            export_artist_name = st.session_state.get("name", f"Artiste #{export_artist_id}")
            st.info(f"👤 Export pour : **{export_artist_name}**")

        st.markdown("---")

        # ── Sélection des sources ─────────────────────────────────────────
        _SOURCE_GROUPS = {
            "Spotify for Artists": [
                "s4a_song_timeline", "s4a_songs_global", "s4a_audience"
            ],
            "Apple Music": [
                "apple_songs_performance", "apple_daily_plays", "apple_listeners"
            ],
            "YouTube": [
                "youtube_channels", "youtube_channel_history", "youtube_videos",
                "youtube_video_stats", "youtube_playlists", "youtube_comments"
            ],
            "SoundCloud": ["soundcloud_tracks_daily"],
            "Instagram": ["instagram_daily_stats"],
            "Meta Ads": ["meta_campaigns", "meta_adsets", "meta_ads", "meta_insights_performance_day"],
            "Hypeddit": ["hypeddit_campaigns", "hypeddit_daily_stats"],
            "Distributeur": ["imusician_monthly_revenue"],
        }

        st.subheader("📋 Sources à inclure")
        col_sel, col_desel = st.columns([1, 5])
        if col_sel.button("Tout sélectionner"):
            for k in _SOURCE_GROUPS:
                st.session_state[f"src_{k}"] = True
        selected_tables: list[str] = []
        cols = st.columns(4)
        for i, (source, tbls) in enumerate(_SOURCE_GROUPS.items()):
            checked = cols[i % 4].checkbox(
                source,
                value=st.session_state.get(f"src_{source}", True),
                key=f"src_{source}",
            )
            if checked:
                selected_tables.extend(tbls)

        if not selected_tables:
            st.warning("Sélectionnez au moins une source.")

        st.caption(f"{len(selected_tables)} table(s) sélectionnée(s) sur {len(_all_table_names())}.")
        st.markdown("---")

        # ── Bouton générer ───────────────────────────────────────────────
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            generate_clicked = st.button(
                "📦 Préparer l'export ZIP",
                type="primary",
                disabled=not selected_tables,
            )

        if generate_clicked:
            db2 = get_db_connection()
            if db2 is None:
                return
            try:
                with st.spinner("Génération du ZIP en cours…"):
                    zip_bytes = export_all(db2, export_artist_id, tables=selected_tables or None)
                st.session_state["_export_csv_bytes"] = zip_bytes.getvalue()
                st.session_state["_export_csv_artist"] = export_artist_name
                st.success("ZIP prêt — cliquez sur Télécharger ci-dessous.")
            except Exception as e:
                st.error(f"Erreur lors de la génération : {e}")
            finally:
                db2.close()

        # ── Bouton télécharger (persiste entre reruns) ───────────────────
        if st.session_state.get("_export_csv_bytes"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = (
                st.session_state.get("_export_csv_artist") or "artiste"
            ).replace(" ", "_").lower()
            filename = f"export_{slug}_{ts}.zip"
            st.download_button(
                label="⬇️ Télécharger le ZIP",
                data=st.session_state["_export_csv_bytes"],
                file_name=filename,
                mime="application/zip",
            )

    finally:
        db.close()
