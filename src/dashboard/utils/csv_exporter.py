"""Utilitaire d'export CSV global — ZIP avec un CSV par table.

Usage:
    from src.dashboard.utils.csv_exporter import export_all
    zip_bytes = export_all(db, artist_id=1)
"""
import io
import zipfile
from datetime import datetime

from src.database.postgres_handler import validate_table

# CSV/Excel formula-injection (CWE-1236) defang: a spreadsheet cell beginning with one
# of these chars is executed as a formula by Excel/Sheets on open. Attacker-controlled
# values (song/campaign names, usernames) reach exports, so prefix such cells with a
# single quote → rendered as inert text.
_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def defang_formulas(df):
    """Return a copy of `df` with every string cell that starts with a formula trigger
    char prefixed by a single quote. Non-string cells untouched. No-op if no object cols."""
    obj_cols = list(df.select_dtypes(include=["object"]).columns)
    if not obj_cols:
        return df
    df = df.copy()
    for c in obj_cols:
        df[c] = df[c].map(
            lambda v: "'" + v if isinstance(v, str) and v[:1] in _FORMULA_LEAD else v
        )
    return df


def _aid(aid: int) -> tuple:
    return (aid,)


def _all_rows(table: str, tenant_column: str = "artist_id") -> str:
    """`SELECT *` of one tenant's rows — for tables whose export needs no filter of
    its own. The name is validated before interpolation (CLAUDE.md rule #8)."""
    validate_table(table)
    return f"SELECT * FROM {table} WHERE {tenant_column} = %s ORDER BY 1"


# (table, sql, params_builder)
# params_builder reçoit artist_id et renvoie un tuple de paramètres pour la query
#
# ⚠️ Depuis le 2026-09-23 (R164), cette liste n'est plus « ce qu'on a pensé à
# exporter » : toute table du locataire y figure OU figure dans `_NOT_EXPORTED` avec
# sa raison. Mesuré ce jour-là : elle couvrait 18 tables de locataire sur 79, sous une
# légende qui promettait « tes données uniquement ». Garde :
# `tests/test_the_export_accounts_for_every_tenant_table.py`.
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
    ("s4a_song_saves_daily", _all_rows("s4a_song_saves_daily"), _aid),
    ("s4a_song_playlist_adds", _all_rows("s4a_song_playlist_adds"), _aid),
    ("s4a_song_discovery_mode", _all_rows("s4a_song_discovery_mode"), _aid),
    ("s4a_song_nonalgo_streams", _all_rows("s4a_song_nonalgo_streams"), _aid),
    ("s4a_artist_radio_count", _all_rows("s4a_artist_radio_count"), _aid),
    ("s4a_song_algo_outcomes", _all_rows("s4a_song_algo_outcomes"), _aid),
    # ── Spotify (API) ────────────────────────────────────────────────────
    # ⚠️ `tracks.artist_id` est l'identifiant SPOTIFY (VARCHAR) : le locataire y est
    # `saas_artist_id`. Filtrer sur `artist_id` rendrait la table d'un autre.
    ("tracks", _all_rows("tracks", "saas_artist_id"), _aid),
    ("track_popularity_history", _all_rows("track_popularity_history"), _aid),
    # ── Apple Music ──────────────────────────────────────────────────────
    # ⚠️ `apple_daily_plays` et `apple_listeners` RETIRÉES le 2026-09-20 (R140 §16.10) :
    # 0 ligne, et AUCUN chemin de code ne les écrit. Les deux parseurs qui les
    # produiraient (`apple_music_csv_parser.py:179` et `:221`) n'ont aucun appelant.
    # Un onglet vide dans un ZIP se lit comme une perte de données, pas comme une
    # absence de source.
    (
        "apple_songs_performance",
        "SELECT * FROM apple_songs_performance WHERE artist_id = %s ORDER BY song_name",
        lambda aid: (aid,),
    ),
    ("apple_songs_history", _all_rows("apple_songs_history"), _aid),
    # ── YouTube ──────────────────────────────────────────────────────────
    # ⚠️ `youtube_playlists` ET `youtube_comments` RETIRÉES le 2026-09-20, même raison :
    # 0 ligne, 0 écrivain. `youtube_comments` n'existe QUE comme schéma
    # (`youtube_schema.py:133`) — trouvée par l'entonnoir du garde, pas par moi.
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
    ("instagram_media", _all_rows("instagram_media"), _aid),
    ("instagram_media_insights", _all_rows("instagram_media_insights"), _aid),
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
    # Les ventilations (âge, pays, placement — au niveau campagne, ensemble et pub).
    ("meta_insights", _all_rows("meta_insights"), _aid),
    ("meta_insights_performance", _all_rows("meta_insights_performance"), _aid),
    ("meta_insights_engagement", _all_rows("meta_insights_engagement"), _aid),
    ("meta_insights_performance_age", _all_rows("meta_insights_performance_age"), _aid),
    ("meta_insights_performance_country", _all_rows("meta_insights_performance_country"), _aid),
    ("meta_insights_performance_placement", _all_rows("meta_insights_performance_placement"), _aid),
    ("meta_insights_performance_ad_age", _all_rows("meta_insights_performance_ad_age"), _aid),
    ("meta_insights_performance_ad_country", _all_rows("meta_insights_performance_ad_country"), _aid),
    ("meta_insights_performance_ad_placement", _all_rows("meta_insights_performance_ad_placement"), _aid),
    ("meta_insights_performance_adset_age", _all_rows("meta_insights_performance_adset_age"), _aid),
    ("meta_insights_performance_adset_country", _all_rows("meta_insights_performance_adset_country"), _aid),
    ("meta_insights_performance_adset_placement", _all_rows("meta_insights_performance_adset_placement"), _aid),
    ("meta_insights_engagement_age", _all_rows("meta_insights_engagement_age"), _aid),
    ("meta_insights_engagement_country", _all_rows("meta_insights_engagement_country"), _aid),
    ("meta_insights_engagement_placement", _all_rows("meta_insights_engagement_placement"), _aid),
    ("meta_insights_engagement_ad_age", _all_rows("meta_insights_engagement_ad_age"), _aid),
    ("meta_insights_engagement_ad_country", _all_rows("meta_insights_engagement_ad_country"), _aid),
    ("meta_insights_engagement_ad_placement", _all_rows("meta_insights_engagement_ad_placement"), _aid),
    ("meta_insights_engagement_adset_age", _all_rows("meta_insights_engagement_adset_age"), _aid),
    ("meta_insights_engagement_adset_country", _all_rows("meta_insights_engagement_adset_country"), _aid),
    ("meta_insights_engagement_adset_placement", _all_rows("meta_insights_engagement_adset_placement"), _aid),
    ("meta_insights_engagement_day", _all_rows("meta_insights_engagement_day"), _aid),
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
    ("imusician_release_summary", _all_rows("imusician_release_summary"), _aid),
    ("imusician_sales_detail", _all_rows("imusician_sales_detail"), _aid),
    ("distrokid_monthly_revenue", _all_rows("distrokid_monthly_revenue"), _aid),
    ("sacem_statement", _all_rows("sacem_statement"), _aid),
    # ── Catalogue (le rapprochement titre ↔ plateformes ↔ campagnes) ─────
    ("track_release_reference", _all_rows("track_release_reference"), _aid),
    ("track_platform_link", _all_rows("track_platform_link"), _aid),
    ("campaign_track_mapping", _all_rows("campaign_track_mapping"), _aid),
    ("campaign_mapping_rejected", _all_rows("campaign_mapping_rejected"), _aid),
    # ── Bilans saisis ou calculés ────────────────────────────────────────
    ("artist_wrapped", _all_rows("artist_wrapped"), _aid),
    ("artist_cost_entries", _all_rows("artist_cost_entries"), _aid),
    # ── Machine Learning ─────────────────────────────────────────────────
    # Per-artist ML scoring history: trigger probabilities, volume forecasts and
    # the full 13-feature input vector (features_json). The `song` column can carry
    # the S4A "Total" row, so the 1x7xxxxxxx filter applies here too.
    (
        "ml_song_predictions",
        "SELECT * FROM ml_song_predictions WHERE artist_id = %s "
        "AND song NOT ILIKE '%%1x7xxxxxxx%%' ORDER BY prediction_date DESC, song",
        lambda aid: (aid,),
    ),
    ("ml_prediction_outcomes", _all_rows("ml_prediction_outcomes"), _aid),
    # Global cohort reference curves (no artist_id) — shipped for context so the
    # exported predictions can be read against the training benchmark.
    (
        "algo_lifecycle_benchmark",
        "SELECT * FROM algo_lifecycle_benchmark "
        "ORDER BY dataset_version DESC, algorithm, age_week_bin_order",
        lambda aid: (),
    ),
]


#: The tenant tables deliberately NOT in the archive, each with the reason. A tenant
#: table in neither list fails the guard: the scope is derived, the exceptions are
#: argued. Account, billing and technical data remain the artist's — they are handed
#: over on request (privacy policy, section 7), not dumped as a spreadsheet.
_CREDENTIAL_BEARING = "secret — empreinte de mot de passe, 2FA ou identifiants chiffrés"
_ACCOUNT = "compte / facturation — communiqué sur demande (Art. 15, contact RGPD)"
_TECHNICAL = "journal technique — communiqué sur demande (Art. 15, contact RGPD)"
_NO_WRITER = "aucun code ne l'alimente — un onglet toujours vide se lit comme une perte"
_NOT_EXPORTED: dict[str, str] = {
    "saas_users": _CREDENTIAL_BEARING,
    "artist_credentials": _CREDENTIAL_BEARING,
    "active_sessions": _CREDENTIAL_BEARING,
    "saas_artists": _ACCOUNT,
    "artist_subscriptions": _ACCOUNT,
    "subscription_plan_history": _ACCOUNT,
    "referral_codes": _ACCOUNT,
    "referral_events": _ACCOUNT,
    "promo_events": _ACCOUNT,
    "app_error_log": _TECHNICAL,
    "etl_run_log": _TECHNICAL,
    "etl_circuit_breaker": _TECHNICAL,
    "csv_upload_log": _TECHNICAL,
    "usage_events": _TECHNICAL,
    "data_revisions": _TECHNICAL,
    "tenant_platform_probe": _TECHNICAL,
    "apple_daily_plays": _NO_WRITER,
    "apple_listeners": _NO_WRITER,
    "youtube_playlists": _NO_WRITER,
    "youtube_comments": _NO_WRITER,
    "youtube_daily_views": _NO_WRITER,
    "s4a_song_playlists": _NO_WRITER,
    "distrokid_sales_detail": _NO_WRITER,
}

#: The checkboxes of the export page — the ONE place a table is given a source.
#: It lived as a second hand list in `views/export_csv.py`, where a table added here
#: and forgotten there could never be ticked.
SOURCE_GROUPS: dict[str, list[str]] = {
    "Spotify for Artists": [
        "s4a_song_timeline", "s4a_songs_global", "s4a_audience", "s4a_song_saves_daily",
        "s4a_song_playlist_adds", "s4a_song_discovery_mode", "s4a_song_nonalgo_streams",
        "s4a_artist_radio_count", "s4a_song_algo_outcomes"],
    "Spotify": ["tracks", "track_popularity_history"],
    "Apple Music": ["apple_songs_performance", "apple_songs_history"],
    "YouTube": ["youtube_channels", "youtube_channel_history", "youtube_videos",
                "youtube_video_stats"],
    "SoundCloud": ["soundcloud_tracks_daily"],
    "Instagram": ["instagram_daily_stats", "instagram_media", "instagram_media_insights"],
    "Meta Ads": ["meta_campaigns", "meta_adsets", "meta_ads",
                 "meta_insights_performance_day", *['meta_insights', 'meta_insights_performance', 'meta_insights_engagement', 'meta_insights_performance_age', 'meta_insights_performance_country', 'meta_insights_performance_placement', 'meta_insights_performance_ad_age', 'meta_insights_performance_ad_country', 'meta_insights_performance_ad_placement', 'meta_insights_performance_adset_age', 'meta_insights_performance_adset_country', 'meta_insights_performance_adset_placement', 'meta_insights_engagement_age', 'meta_insights_engagement_country', 'meta_insights_engagement_placement', 'meta_insights_engagement_ad_age', 'meta_insights_engagement_ad_country', 'meta_insights_engagement_ad_placement', 'meta_insights_engagement_adset_age', 'meta_insights_engagement_adset_country', 'meta_insights_engagement_adset_placement', 'meta_insights_engagement_day']],
    "Hypeddit": ["hypeddit_campaigns", "hypeddit_daily_stats"],
    "Distributeur": ["imusician_monthly_revenue", "imusician_release_summary",
                     "imusician_sales_detail", "distrokid_monthly_revenue"],
    "SACEM": ["sacem_statement"],
    "Catalogue": ["track_release_reference", "track_platform_link",
                  "campaign_track_mapping", "campaign_mapping_rejected"],
    "Bilans": ["artist_wrapped", "artist_cost_entries"],
    "Machine Learning": ["ml_song_predictions", "ml_prediction_outcomes",
                         "algo_lifecycle_benchmark"],
}


def export_excel(db, artist_id: int, tables: list[str] | None = None) -> io.BytesIO:
    """Exporte toutes les tables pour un artiste dans un fichier Excel (un onglet par table).

    Requires openpyxl: pip install openpyxl
    """
    import pandas as pd

    selected = set(tables) if tables is not None else None
    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        for table_name, sql, params_builder in _TABLES:
            if selected is not None and table_name not in selected:
                continue
            try:
                df = db.fetch_df(sql, params_builder(artist_id))
                defang_formulas(df).to_excel(writer, sheet_name=table_name[:31], index=False)
            except Exception:
                continue

    excel_buffer.seek(0)
    return excel_buffer


def table_names() -> list[str]:
    """Return the ordered list of all exportable table names."""
    return [t for t, _, _ in _TABLES]


def export_all(db, artist_id: int, tables: list[str] | None = None) -> io.BytesIO:
    """Exporte toutes les tables pour un artiste dans un ZIP (un CSV par table).

    Args:
        db: PostgresHandler connecté.
        artist_id: ID de l'artiste à exporter (obligatoire).
        tables: Optional list of table names to include. None = all tables.

    Returns:
        io.BytesIO contenant le ZIP, prêt pour st.download_button.
    """
    selected = set(tables) if tables is not None else None
    zip_buffer = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exported: list[str] = []
    empty: list[str] = []

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for table_name, sql, params_builder in _TABLES:
            if selected is not None and table_name not in selected:
                continue
            try:
                df = db.fetch_df(sql, params_builder(artist_id))
            except Exception:
                # Table absente ou erreur → on saute silencieusement
                empty.append(table_name)
                continue

            csv_buf = io.StringIO()
            defang_formulas(df).to_csv(csv_buf, index=False)
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
