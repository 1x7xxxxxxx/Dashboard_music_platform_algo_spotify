"""Utilitaire d'export CSV global — ZIP avec un CSV par table.

Usage:
    from src.dashboard.utils.csv_exporter import export_all
    zip_bytes = export_all(db, artist_id=1)
"""
import io
import zipfile
from datetime import datetime


# (table, sql, params_builder)
# params_builder reçoit artist_id et renvoie un tuple de paramètres pour la query
_TABLES = [
    # ── Spotify for Artists ──────────────────────────────────────────────
    (
        "s4a_song_timeline",
        "SELECT * FROM s4a_song_timeline WHERE artist_id = %s AND song NOT ILIKE '%%1x7xxxxxxx%%' ORDER BY date, song",
        lambda aid: (aid,),
    ),
    (
        "s4a_songs_global",
        "SELECT * FROM s4a_songs_global WHERE artist_id = %s ORDER BY song",
        lambda aid: (aid,),
    ),
    (
        "s4a_audience",
        "SELECT * FROM s4a_audience WHERE artist_id = %s ORDER BY date",
        lambda aid: (aid,),
    ),
    # ── Apple Music ──────────────────────────────────────────────────────
    (
        "apple_songs_performance",
        "SELECT * FROM apple_songs_performance WHERE artist_id = %s ORDER BY song_name",
        lambda aid: (aid,),
    ),
    (
        "apple_daily_plays",
        "SELECT * FROM apple_daily_plays WHERE artist_id = %s ORDER BY date, song_name",
        lambda aid: (aid,),
    ),
    (
        "apple_listeners",
        "SELECT * FROM apple_listeners WHERE artist_id = %s ORDER BY date",
        lambda aid: (aid,),
    ),
    # ── YouTube ──────────────────────────────────────────────────────────
    (
        "youtube_channels",
        "SELECT * FROM youtube_channels WHERE artist_id = %s ORDER BY channel_id",
        lambda aid: (aid,),
    ),
    (
        "youtube_channel_history",
        "SELECT * FROM youtube_channel_history WHERE artist_id = %s ORDER BY collected_at",
        lambda aid: (aid,),
    ),
    (
        "youtube_videos",
        "SELECT * FROM youtube_videos WHERE artist_id = %s ORDER BY published_at DESC",
        lambda aid: (aid,),
    ),
    (
        "youtube_video_stats",
        "SELECT * FROM youtube_video_stats WHERE artist_id = %s ORDER BY collected_at DESC",
        lambda aid: (aid,),
    ),
    (
        "youtube_playlists",
        "SELECT * FROM youtube_playlists WHERE artist_id = %s ORDER BY playlist_id",
        lambda aid: (aid,),
    ),
    (
        "youtube_comments",
        "SELECT * FROM youtube_comments WHERE artist_id = %s ORDER BY published_at DESC",
        lambda aid: (aid,),
    ),
    # ── SoundCloud ───────────────────────────────────────────────────────
    (
        "soundcloud_tracks_daily",
        "SELECT * FROM soundcloud_tracks_daily WHERE artist_id = %s ORDER BY collected_at DESC",
        lambda aid: (aid,),
    ),
    # ── Instagram ────────────────────────────────────────────────────────
    (
        "instagram_daily_stats",
        "SELECT * FROM instagram_daily_stats WHERE artist_id = %s ORDER BY collected_at DESC",
        lambda aid: (aid,),
    ),
    # ── Meta Ads ─────────────────────────────────────────────────────────
    (
        "meta_campaigns",
        "SELECT * FROM meta_campaigns WHERE artist_id = %s ORDER BY campaign_id",
        lambda aid: (aid,),
    ),
    (
        "meta_adsets",
        "SELECT * FROM meta_adsets WHERE artist_id = %s ORDER BY adset_id",
        lambda aid: (aid,),
    ),
    (
        "meta_ads",
        "SELECT * FROM meta_ads WHERE artist_id = %s ORDER BY ad_id",
        lambda aid: (aid,),
    ),
    (
        "meta_insights_performance_day",
        "SELECT * FROM meta_insights_performance_day WHERE artist_id = %s ORDER BY day_date",
        lambda aid: (aid,),
    ),
    # ── Hypeddit ─────────────────────────────────────────────────────────
    (
        "hypeddit_campaigns",
        "SELECT * FROM hypeddit_campaigns WHERE artist_id = %s ORDER BY campaign_name",
        lambda aid: (aid,),
    ),
    (
        "hypeddit_daily_stats",
        "SELECT * FROM hypeddit_daily_stats WHERE artist_id = %s ORDER BY date, campaign_name",
        lambda aid: (aid,),
    ),
    # ── iMusician ────────────────────────────────────────────────────────
    (
        "imusician_monthly_revenue",
        "SELECT * FROM imusician_monthly_revenue WHERE artist_id = %s ORDER BY year, month",
        lambda aid: (aid,),
    ),
]


def export_all(db, artist_id: int) -> io.BytesIO:
    """Exporte toutes les tables pour un artiste dans un ZIP (un CSV par table).

    Args:
        db: PostgresHandler connecté.
        artist_id: ID de l'artiste à exporter (obligatoire).

    Returns:
        io.BytesIO contenant le ZIP, prêt pour st.download_button.
    """
    zip_buffer = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exported: list[str] = []
    empty: list[str] = []

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for table_name, sql, params_builder in _TABLES:
            try:
                df = db.fetch_df(sql, params_builder(artist_id))
            except Exception:
                # Table absente ou erreur → on saute silencieusement
                empty.append(table_name)
                continue

            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            zf.writestr(f"{table_name}.csv", csv_buf.getvalue())

            if df.empty:
                empty.append(table_name)
            else:
                exported.append(table_name)

        # Fichier index récapitulatif
        summary_lines = [
            f"Export généré le {timestamp}",
            f"artist_id = {artist_id}",
            "",
            f"Tables avec données ({len(exported)}) :",
        ] + [f"  - {t}" for t in exported] + [
            "",
            f"Tables vides / absentes ({len(empty)}) :",
        ] + [f"  - {t}" for t in empty]
        zf.writestr("_index.txt", "\n".join(summary_lines))

    zip_buffer.seek(0)
    return zip_buffer
