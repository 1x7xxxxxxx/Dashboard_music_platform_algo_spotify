"""Fonctions KPI réutilisables par toutes les views du dashboard."""
from datetime import datetime, timedelta, date


# Seuils de fraîcheur (en heures)
_FRESH_H = 24
_WARN_H = 72

# Filtre ligne "Total" des CSV Spotify for Artists
ARTIST_NAME_FILTER = "1x7xxxxxxx"


# ─── Fraîcheur des sources ──────────────────────────────────────────────────

SOURCES_CONFIG = [
    {
        "label": "Spotify S4A",
        "icon": "🎵",
        "table": "s4a_song_timeline",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "YouTube",
        "icon": "🎬",
        "table": "youtube_channel_history",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "SoundCloud",
        "icon": "☁️",
        "table": "soundcloud_tracks_daily",
        "col": "collected_at",  # DATE
        "artist_col": "artist_id",
    },
    {
        "label": "Instagram",
        "icon": "📸",
        "table": "instagram_daily_stats",
        "col": "collected_at",  # DATE
        "artist_col": "artist_id",
    },
    {
        "label": "Apple Music",
        "icon": "🍎",
        "table": "apple_songs_performance",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "Meta Ads",
        "icon": "📱",
        "table": "meta_insights_performance_day",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "iMusician",
        "icon": "💰",
        "table": "imusician_monthly_revenue",
        "col": "updated_at",
        "artist_col": "artist_id",
    },
]


def get_source_freshness(db, artist_id):
    """
    Retourne un dict {label: last_dt} pour chaque source.
    last_dt peut être None si aucune donnée.
    """
    result = {}
    for src in SOURCES_CONFIG:
        try:
            if artist_id is not None:
                row = db.fetch_query(
                    f"SELECT MAX({src['col']}) FROM {src['table']} WHERE {src['artist_col']} = %s",
                    (artist_id,)
                )
            else:
                row = db.fetch_query(
                    f"SELECT MAX({src['col']}) FROM {src['table']}"
                )
            val = row[0][0] if row and row[0][0] is not None else None
            # Normaliser en datetime
            if val is not None and not isinstance(val, datetime):
                val = datetime(val.year, val.month, val.day, 0, 0, 0)
            result[src['label']] = {'icon': src['icon'], 'last_dt': val}
        except Exception:
            result[src['label']] = {'icon': src['icon'], 'last_dt': None}
    return result


def freshness_status(last_dt):
    """
    Retourne (emoji, color, label) selon l'âge de last_dt.
    """
    if last_dt is None:
        return "⚫", "#888888", "Pas de données"
    age_h = (datetime.now() - last_dt).total_seconds() / 3600
    if age_h < _FRESH_H:
        return "🟢", "#1DB954", f"Il y a {int(age_h)}h"
    elif age_h < _WARN_H:
        days = int(age_h / 24)
        return "🟠", "#FFA500", f"Il y a {days}j"
    else:
        days = int(age_h / 24)
        return "🔴", "#FF4444", f"Il y a {days}j"


# ─── KPI Streams ────────────────────────────────────────────────────────────

def get_total_streams_s4a(db, artist_id):
    """Total streams Spotify S4A (dédupliqué par MAX/jour/chanson)."""
    try:
        if artist_id is not None:
            q = f"""
                SELECT SUM(daily_max) FROM (
                    SELECT MAX(streams) AS daily_max
                    FROM s4a_song_timeline
                    WHERE song NOT ILIKE %s AND artist_id = %s
                    GROUP BY date, song
                ) sub
            """
            row = db.fetch_query(q, (f"%{ARTIST_NAME_FILTER}%", artist_id))
        else:
            q = f"""
                SELECT SUM(daily_max) FROM (
                    SELECT MAX(streams) AS daily_max
                    FROM s4a_song_timeline
                    WHERE song NOT ILIKE %s
                    GROUP BY date, song
                ) sub
            """
            row = db.fetch_query(q, (f"%{ARTIST_NAME_FILTER}%",))
        return int(row[0][0] or 0)
    except Exception:
        return 0


def get_total_views_youtube(db, artist_id):
    """Total vues YouTube (compteur global chaîne, dernière valeur)."""
    try:
        if artist_id is not None:
            q = "SELECT view_count FROM youtube_channel_history WHERE artist_id = %s ORDER BY collected_at DESC LIMIT 1"
            row = db.fetch_query(q, (artist_id,))
        else:
            q = "SELECT view_count FROM youtube_channel_history ORDER BY collected_at DESC LIMIT 1"
            row = db.fetch_query(q)
        return int(row[0][0] or 0)
    except Exception:
        return 0


def get_total_plays_soundcloud(db, artist_id):
    """Total plays SoundCloud (dernière snapshot disponible)."""
    try:
        if artist_id is not None:
            q = """
                SELECT SUM(playback_count) FROM (
                    SELECT DISTINCT ON (track_id) playback_count
                    FROM soundcloud_tracks_daily
                    WHERE artist_id = %s
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q, (artist_id,))
        else:
            q = """
                SELECT SUM(playback_count) FROM (
                    SELECT DISTINCT ON (track_id) playback_count
                    FROM soundcloud_tracks_daily
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q)
        return int(row[0][0] or 0)
    except Exception:
        return 0


def get_total_plays_apple(db, artist_id):
    """Total plays Apple Music."""
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT SUM(plays) FROM apple_songs_performance WHERE artist_id = %s",
                (artist_id,)
            )
        else:
            row = db.fetch_query("SELECT SUM(plays) FROM apple_songs_performance")
        return int(row[0][0] or 0)
    except Exception:
        return 0


# ─── KPI ML ─────────────────────────────────────────────────────────────────

def get_spotify_popularity(db, artist_id):
    """Score de popularité Spotify (dernier enregistrement)."""
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT popularity, track_name FROM track_popularity_history WHERE artist_id = %s ORDER BY date DESC LIMIT 1",
                (artist_id,)
            )
        else:
            row = db.fetch_query(
                "SELECT popularity, track_name FROM track_popularity_history ORDER BY date DESC LIMIT 1"
            )
        if row and row[0][0] is not None:
            return {'score': int(row[0][0]), 'track': row[0][1]}
    except Exception:
        pass
    return None


def get_instagram_followers(db, artist_id):
    """Nombre d'abonnés Instagram (dernier snapshot)."""
    try:
        if artist_id is not None:
            row = db.fetch_query(
                """SELECT followers_count, collected_at FROM instagram_daily_stats
                   WHERE artist_id = %s ORDER BY collected_at DESC LIMIT 1""",
                (artist_id,)
            )
        else:
            row = db.fetch_query(
                "SELECT followers_count, collected_at FROM instagram_daily_stats ORDER BY collected_at DESC LIMIT 1"
            )
        if row and row[0][0] is not None:
            return {'followers': int(row[0][0]), 'date': row[0][1]}
    except Exception:
        pass
    return None


def get_soundcloud_likes(db, artist_id):
    """Total likes SoundCloud (dernière snapshot)."""
    try:
        if artist_id is not None:
            q = """
                SELECT SUM(likes_count) FROM (
                    SELECT DISTINCT ON (track_id) likes_count
                    FROM soundcloud_tracks_daily
                    WHERE artist_id = %s
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q, (artist_id,))
        else:
            q = """
                SELECT SUM(likes_count) FROM (
                    SELECT DISTINCT ON (track_id) likes_count
                    FROM soundcloud_tracks_daily
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q)
        return int(row[0][0] or 0)
    except Exception:
        return 0


# ─── ROI Breakheaven ─────────────────────────────────────────────────────────

def get_roi_data(db, artist_id, from_date, to_date):
    """
    Calcule le ROI iMusician / Meta Ads pour une période donnée.
    Retourne un dict avec revenue_eur, meta_spend, roi_pct, breakeven_date.
    """
    result = {
        'revenue_eur': 0.0,
        'meta_spend': 0.0,
        'roi_pct': None,
        'profitable': False,
    }

    # Revenus iMusician (aggregation sur year+month)
    try:
        if artist_id is not None:
            row = db.fetch_query(
                """SELECT COALESCE(SUM(revenue_eur), 0)
                   FROM imusician_monthly_revenue
                   WHERE artist_id = %s
                     AND make_date(year, month, 1) BETWEEN %s AND %s""",
                (artist_id, from_date, to_date)
            )
        else:
            row = db.fetch_query(
                """SELECT COALESCE(SUM(revenue_eur), 0)
                   FROM imusician_monthly_revenue
                   WHERE make_date(year, month, 1) BETWEEN %s AND %s""",
                (from_date, to_date)
            )
        result['revenue_eur'] = float(row[0][0] or 0)
    except Exception:
        pass

    # Dépenses Meta Ads
    try:
        if artist_id is not None:
            row = db.fetch_query(
                """SELECT COALESCE(SUM(spend), 0) FROM meta_insights_performance_day
                   WHERE artist_id = %s AND day_date BETWEEN %s AND %s""",
                (artist_id, from_date, to_date)
            )
        else:
            row = db.fetch_query(
                """SELECT COALESCE(SUM(spend), 0) FROM meta_insights_performance_day
                   WHERE day_date BETWEEN %s AND %s""",
                (from_date, to_date)
            )
        result['meta_spend'] = float(row[0][0] or 0)
    except Exception:
        pass

    if result['meta_spend'] > 0:
        result['roi_pct'] = (result['revenue_eur'] / result['meta_spend']) * 100
        result['profitable'] = result['revenue_eur'] >= result['meta_spend']

    return result


def get_monthly_roi_series(db, artist_id, from_date, to_date):
    """
    Retourne un DataFrame mensuel revenue vs spend pour la période.
    Colonnes : period_date, revenue_eur, meta_spend
    """
    import pandas as pd

    # Revenue par mois
    try:
        if artist_id is not None:
            df_rev = db.fetch_df(
                """SELECT make_date(year, month, 1) AS period_date, SUM(revenue_eur) AS revenue_eur
                   FROM imusician_monthly_revenue
                   WHERE artist_id = %s AND make_date(year, month, 1) BETWEEN %s AND %s
                   GROUP BY year, month ORDER BY year, month""",
                (artist_id, from_date, to_date)
            )
        else:
            df_rev = db.fetch_df(
                """SELECT make_date(year, month, 1) AS period_date, SUM(revenue_eur) AS revenue_eur
                   FROM imusician_monthly_revenue
                   WHERE make_date(year, month, 1) BETWEEN %s AND %s
                   GROUP BY year, month ORDER BY year, month""",
                (from_date, to_date)
            )
    except Exception:
        df_rev = pd.DataFrame(columns=['period_date', 'revenue_eur'])

    # Dépenses Meta par mois
    try:
        if artist_id is not None:
            df_spend = db.fetch_df(
                """SELECT DATE_TRUNC('month', day_date)::date AS period_date, SUM(spend) AS meta_spend
                   FROM meta_insights_performance_day
                   WHERE artist_id = %s AND day_date BETWEEN %s AND %s
                   GROUP BY DATE_TRUNC('month', day_date) ORDER BY 1""",
                (artist_id, from_date, to_date)
            )
        else:
            df_spend = db.fetch_df(
                """SELECT DATE_TRUNC('month', day_date)::date AS period_date, SUM(spend) AS meta_spend
                   FROM meta_insights_performance_day
                   WHERE day_date BETWEEN %s AND %s
                   GROUP BY DATE_TRUNC('month', day_date) ORDER BY 1""",
                (from_date, to_date)
            )
    except Exception:
        df_spend = pd.DataFrame(columns=['period_date', 'meta_spend'])

    if df_rev.empty and df_spend.empty:
        return pd.DataFrame()

    if df_rev.empty:
        df_rev = pd.DataFrame(columns=['period_date', 'revenue_eur'])
    if df_spend.empty:
        df_spend = pd.DataFrame(columns=['period_date', 'meta_spend'])

    df = pd.merge(df_rev, df_spend, on='period_date', how='outer').fillna(0)
    df['period_date'] = pd.to_datetime(df['period_date'])
    return df.sort_values('period_date')
