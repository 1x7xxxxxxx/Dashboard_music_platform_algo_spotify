"""PDF export — collectors layer (move-only split of pdf_exporter)."""
from datetime import timedelta
from src.utils.track_matching import track_title_matches, canonical_song_sql
from src.dashboard.utils.kpi_helpers import (
    ARTIST_NAME_FILTER,
)



def _latest_release(db, artist_id):
    """Latest released track in the timeline ('_') form, or None."""
    try:
        rows = db.fetch_query(
            "SELECT REPLACE(track_name, '?', '_') FROM tracks "
            "WHERE saas_artist_id = %s AND release_date IS NOT NULL "
            "ORDER BY release_date DESC LIMIT 1",
            (artist_id,))
        return rows[0][0] if rows else None
    except Exception:
        return None


def _get_artist_name(db, artist_id):
    if artist_id is None:
        return "Tous les artistes"
    try:
        row = db.fetch_query("SELECT name FROM saas_artists WHERE id = %s", (artist_id,))
        return row[0][0] if row else f"Artiste #{artist_id}"
    except Exception:
        return f"Artiste #{artist_id}"


def get_available_songs(db, artist_id):
    """Retourne la liste des chansons disponibles pour un artiste (triées par streams desc)."""
    try:
        if artist_id is not None:
            rows = db.fetch_query(
                """SELECT song, SUM(streams) AS total
                   FROM s4a_song_timeline
                   WHERE artist_id = %s AND song NOT ILIKE %s
                   GROUP BY song ORDER BY total DESC""",
                (artist_id, f"%{ARTIST_NAME_FILTER}%")
            )
        else:
            rows = db.fetch_query(
                """SELECT song, SUM(streams) AS total
                   FROM s4a_song_timeline
                   WHERE song NOT ILIKE %s
                   GROUP BY song ORDER BY total DESC""",
                (f"%{ARTIST_NAME_FILTER}%",)
            )
        return [r[0] for r in rows] if rows else []
    except Exception:
        return []


def get_artists_list(db):
    """Retourne [{id, name}] pour tous les artistes actifs."""
    try:
        rows = db.fetch_query(
            "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
        )
        return [{'id': r[0], 'name': r[1]} for r in rows] if rows else []
    except Exception:
        return []


def _collect_songs_focus(db, artist_id, songs, from_date, to_date):
    """
    Pour chaque chanson sélectionnée, retourne un dict avec :
    - total_streams_period, last7d_streams
    - ML predictions (si disponibles)
    """
    result = []
    for song in songs:
        entry = {'song': song, 'total_streams': 0, 'last7d_streams': 0, 'ml': None}

        # Streams sur la période
        try:
            if artist_id is not None:
                row = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0)
                       FROM s4a_song_timeline
                       WHERE song = %s AND song NOT ILIKE %s AND artist_id = %s AND date BETWEEN %s AND %s""",
                    (song, f"%{ARTIST_NAME_FILTER}%", artist_id, from_date, to_date)
                )
            else:
                row = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0)
                       FROM s4a_song_timeline
                       WHERE song = %s AND song NOT ILIKE %s AND date BETWEEN %s AND %s""",
                    (song, f"%{ARTIST_NAME_FILTER}%", from_date, to_date)
                )
            entry['total_streams'] = int(row[0][0] or 0)
        except Exception:
            pass

        # Streams 7 derniers jours
        try:
            if artist_id is not None:
                row = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0)
                       FROM s4a_song_timeline
                       WHERE song = %s AND song NOT ILIKE %s AND artist_id = %s
                         AND date >= CURRENT_DATE - INTERVAL '7 days'""",
                    (song, f"%{ARTIST_NAME_FILTER}%", artist_id)
                )
            else:
                row = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0)
                       FROM s4a_song_timeline
                       WHERE song = %s AND song NOT ILIKE %s AND date >= CURRENT_DATE - INTERVAL '7 days'""",
                    (song, f"%{ARTIST_NAME_FILTER}%")
                )
            entry['last7d_streams'] = int(row[0][0] or 0)
        except Exception:
            pass

        # ML predictions
        try:
            if artist_id is not None:
                row = db.fetch_query(
                    """SELECT dw_prob, rr_prob, radio_prob,
                              dw_forecast_7d, rr_forecast_7d, prediction_date
                       FROM ml_song_predictions
                       WHERE song = %s AND artist_id = %s
                       ORDER BY prediction_date DESC LIMIT 1""",
                    (song, artist_id)
                )
            else:
                row = db.fetch_query(
                    """SELECT dw_prob, rr_prob, radio_prob,
                              dw_forecast_7d, rr_forecast_7d, prediction_date
                       FROM ml_song_predictions
                       WHERE song = %s
                       ORDER BY prediction_date DESC LIMIT 1""",
                    (song,)
                )
            if row and row[0][0] is not None:
                entry['ml'] = {
                    'dw_prob':       float(row[0][0] or 0),
                    'rr_prob':       float(row[0][1] or 0),
                    'radio_prob':    float(row[0][2] or 0),
                    'dw_forecast':   float(row[0][3] or 0),
                    'rr_forecast':   float(row[0][4] or 0),
                    'prediction_date': str(row[0][5]),
                }
        except Exception:
            pass

        result.append(entry)
    return result


def _collect_s4a_top_songs(db, artist_id, from_date, to_date, songs_filter=None):
    """Top 15 chansons S4A sur la période + streams 7 derniers jours.
    songs_filter: liste optionnelle de noms de chansons — None = toutes.
    """
    try:
        song_clause = ""
        song_params: tuple = ()
        if songs_filter:
            placeholders = ",".join(["%s"] * len(songs_filter))
            song_clause = f"AND song IN ({placeholders})"
            song_params = tuple(songs_filter)

        if artist_id is not None:
            rows = db.fetch_query(
                f"""SELECT song, SUM(streams) AS total
                   FROM (
                       SELECT DISTINCT ON (date, song) song, streams
                       FROM s4a_song_timeline
                       WHERE song NOT ILIKE %s AND artist_id = %s
                         AND date BETWEEN %s AND %s {song_clause}
                       ORDER BY date, song, collected_at DESC
                   ) sub
                   GROUP BY song ORDER BY total DESC LIMIT 15""",
                (f"%{ARTIST_NAME_FILTER}%", artist_id, from_date, to_date, *song_params),
            )
        else:
            rows = db.fetch_query(
                f"""SELECT song, SUM(streams) AS total
                   FROM (
                       SELECT DISTINCT ON (date, song) song, streams
                       FROM s4a_song_timeline
                       WHERE song NOT ILIKE %s AND date BETWEEN %s AND %s {song_clause}
                       ORDER BY date, song, collected_at DESC
                   ) sub
                   GROUP BY song ORDER BY total DESC LIMIT 15""",
                (f"%{ARTIST_NAME_FILTER}%", from_date, to_date, *song_params),
            )
        if not rows:
            return []
        songs_list = [r[0] for r in rows]
        last7_map = {}
        for song in songs_list:
            if artist_id is not None:
                r7 = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline
                       WHERE song = %s AND song NOT ILIKE %s AND artist_id = %s
                         AND date >= CURRENT_DATE - INTERVAL '7 days'""",
                    (song, f"%{ARTIST_NAME_FILTER}%", artist_id),
                )
            else:
                r7 = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline
                       WHERE song = %s AND song NOT ILIKE %s
                         AND date >= CURRENT_DATE - INTERVAL '7 days'""",
                    (song, f"%{ARTIST_NAME_FILTER}%"),
                )
            last7_map[song] = int(r7[0][0] or 0) if r7 else 0
        return [(r[0], int(r[1] or 0), last7_map.get(r[0], 0)) for r in rows]
    except Exception:
        return []


def _collect_youtube(db, artist_id, single_song=None):
    """Stats chaîne + top 10 vidéos par vues (filtré sur la vidéo de la track si donnée)."""
    if artist_id is None:
        return None
    try:
        ch = db.fetch_query(
            """SELECT MAX(subscriber_count), MAX(view_count)
               FROM youtube_channel_history WHERE artist_id = %s""",
            (artist_id,),
        )
        subs  = int(ch[0][0] or 0) if ch else 0
        views = int(ch[0][1] or 0) if ch else 0
        vids  = db.fetch_query(
            """SELECT v.title, v.published_at,
                      vs.view_count, vs.like_count, vs.comment_count
               FROM youtube_videos v
               JOIN (
                   SELECT video_id, MAX(collected_at) AS max_date
                   FROM youtube_video_stats WHERE artist_id = %s GROUP BY video_id
               ) latest ON v.video_id = latest.video_id
               JOIN youtube_video_stats vs
                   ON vs.video_id = latest.video_id
                  AND vs.collected_at = latest.max_date
               WHERE v.artist_id = %s
               ORDER BY vs.view_count DESC LIMIT 10""",
            (artist_id, artist_id),
        )
        videos = [
            (r[0], str(r[1])[:10] if r[1] else '—',
             int(r[2] or 0), int(r[3] or 0), int(r[4] or 0))
            for r in (vids or [])
        ]
        if single_song:
            videos = [v for v in videos if track_title_matches(single_song, v[0])]
        return {
            'subscriber_count': subs,
            'total_views':      views,
            'videos':           videos,
            'single':           bool(single_song),
        }
    except Exception:
        return None


def _collect_instagram(db, artist_id, from_date, to_date):
    """Derniers stats + historique des abonnés sur la période sélectionnée."""
    if artist_id is None:
        return None
    try:
        latest = db.fetch_query(
            """SELECT DISTINCT ON (ig_user_id)
                   username, followers_count, media_count
               FROM instagram_daily_stats WHERE artist_id = %s
               ORDER BY ig_user_id, collected_at DESC""",
            (artist_id,),
        )
        if not latest:
            return None
        username, followers, media_count = latest[0]
        history = db.fetch_query(
            """SELECT collected_at::date, MAX(followers_count)
               FROM instagram_daily_stats
               WHERE artist_id = %s AND collected_at::date BETWEEN %s AND %s
               GROUP BY collected_at::date ORDER BY collected_at::date""",
            (artist_id, from_date, to_date),
        )
        return {
            'username':    username or '—',
            'followers':   int(followers or 0),
            'media_count': int(media_count or 0),
            'history':     [(str(r[0]), int(r[1] or 0)) for r in history] if history else [],
        }
    except Exception:
        return None


def _collect_meta(db, artist_id, from_date, to_date):
    """Résumé Meta Ads sur la période — source meta_insights_performance_day
    (autoritative, dédupliquée, = get_roi_data). L'ancienne table agrégée
    meta_insights_performance double-comptait les fenêtres (≈2× le spend réel)."""
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            """SELECT campaign_name,
                      SUM(spend)       AS spend,
                      SUM(results)     AS results,
                      SUM(impressions) AS impressions,
                      SUM(reach)       AS reach,
                      SUM(spend) / NULLIF(SUM(results), 0) AS cpr
               FROM meta_insights_performance_day
               WHERE artist_id = %s AND day_date BETWEEN %s AND %s
               GROUP BY campaign_name
               ORDER BY spend DESC
               LIMIT 10""",
            (artist_id, from_date, to_date),
        )
        if not rows:
            return None
        campaigns = [
            (r[0], float(r[1] or 0), int(r[2] or 0),
             int(r[3] or 0), int(r[4] or 0), float(r[5] or 0))
            for r in rows
        ]
        # Totals from the SAME period-filtered day table (all campaigns, not just top 10).
        tot = db.fetch_query(
            """SELECT COALESCE(SUM(spend), 0), COALESCE(SUM(results), 0)
               FROM meta_insights_performance_day
               WHERE artist_id = %s AND day_date BETWEEN %s AND %s""",
            (artist_id, from_date, to_date),
        )
        return {
            'campaigns':     campaigns,
            'total_spend':   float(tot[0][0] or 0) if tot else 0.0,
            'total_results': int(tot[0][1] or 0) if tot else 0,
        }
    except Exception:
        return None


def _collect_soundcloud_tracks(db, artist_id, single_song=None):
    """Latest snapshot per track (sorted by plays). Fetch-all then Python-filter to
    the selected track via the robust cross-platform matcher (reliable vs ILIKE)."""
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            """SELECT DISTINCT ON (track_id)
                   title, playback_count, likes_count, reposts_count, comment_count
               FROM soundcloud_tracks_daily WHERE artist_id = %s
               ORDER BY track_id, collected_at DESC""",
            (artist_id,),
        )
    except Exception:
        return []
    rows = rows or []
    if single_song:
        rows = [r for r in rows if track_title_matches(single_song, r[0])]
    return sorted(
        [(r[0], int(r[1] or 0), int(r[2] or 0), int(r[3] or 0), int(r[4] or 0))
         for r in rows],
        key=lambda x: -x[1],
    )


def _collect_apple(db, artist_id, selected_songs=None):
    """Apple totals + top songs (with shazams). Fetch-all then Python-filter to the
    SELECTED tracks (1 or N) via the robust cross-platform matcher."""
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            "SELECT song_name, plays, shazam_count FROM apple_songs_performance "
            "WHERE artist_id = %s ORDER BY plays DESC", (artist_id,))
    except Exception:
        return None
    rows = rows or []
    sel = list(selected_songs or [])
    if sel:
        rows = [r for r in rows if any(track_title_matches(s, r[0]) for s in sel)]
    songs = [(r[0], int(r[1] or 0), int(r[2] or 0)) for r in rows]
    return {
        'total_plays':   sum(s[1] for s in songs),
        'total_shazams': sum(s[2] for s in songs),
        'top_songs':     songs[:10],
        'matched':       len(songs),
    }


def _collect_hypeddit(db, artist_id, from_date, to_date):
    """Séries journalières Hypeddit (visites/clics/budget) sur la période."""
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            """SELECT date::text, SUM(visits), SUM(clicks), SUM(budget)
               FROM hypeddit_daily_stats
               WHERE artist_id = %s AND date BETWEEN %s AND %s
               GROUP BY date ORDER BY date""",
            (artist_id, from_date, to_date))
        if not rows:
            return None
        series = [(r[0], int(r[1] or 0), int(r[2] or 0), float(r[3] or 0)) for r in rows]
        return {
            'series': series,
            'total_visits': sum(s[1] for s in series),
            'total_clicks': sum(s[2] for s in series),
            'total_budget': sum(s[3] for s in series),
        }
    except Exception:
        return None


def _collect_hypeddit_campaigns(db, artist_id, from_date, to_date):
    """Budget total par campagne Hypeddit (barres)."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            """SELECT campaign_name, SUM(budget) FROM hypeddit_daily_stats
               WHERE artist_id = %s AND date BETWEEN %s AND %s
               GROUP BY campaign_name ORDER BY SUM(budget) DESC""",
            (artist_id, from_date, to_date))
        return [(r[0], float(r[1] or 0)) for r in rows] if rows else []
    except Exception:
        return []


def _collect_playlist_adds_windows(db, artist_id, song):
    """Latest playlist-add count per window (7d/28d/12m) for one song."""
    if artist_id is None or not song:
        return {}
    try:
        rows = db.fetch_query(
            """SELECT DISTINCT ON (time_window) time_window, count
               FROM s4a_song_playlist_adds
               WHERE artist_id = %s AND song = %s AND time_window IN ('7d','28d','12m')
               ORDER BY time_window, recorded_at DESC""",
            (artist_id, song))
        return {r[0]: int(r[1] or 0) for r in (rows or [])}
    except Exception:
        return {}


_BREAKDOWN_DIMS = {
    'country':   ('meta_insights_performance_country', 'country'),
    'placement': ('meta_insights_performance_placement', 'placement'),
    'age':       ('meta_insights_performance_age', 'age_range'),
}


def _collect_meta_breakdowns(db, artist_id):
    """Dépense Meta par pays/placement/âge — déduplique les snapshots avant SUM."""
    if artist_id is None:
        return None
    out = {}
    for key, (table, col) in _BREAKDOWN_DIMS.items():
        try:
            rows = db.fetch_query(
                f"""SELECT {col}, SUM(spend) AS spend FROM (
                        SELECT DISTINCT ON (campaign_name, {col}) {col}, spend
                        FROM {table} WHERE artist_id = %s
                        ORDER BY campaign_name, {col}, collected_at DESC
                    ) t WHERE {col} IS NOT NULL
                    GROUP BY {col} ORDER BY spend DESC LIMIT 8""",
                (artist_id,))
            out[key] = [(r[0], float(r[1] or 0)) for r in rows] if rows else []
        except Exception:
            out[key] = []
    return out if any(out.values()) else None


def _collect_revenue_forecast(db, artist_id):
    """Série mensuelle de revenus iMusician (pour bars + projection)."""
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            """SELECT make_date(year, month, 1)::text, SUM(revenue_eur)
               FROM imusician_monthly_revenue WHERE artist_id = %s
               GROUP BY year, month ORDER BY year, month""",
            (artist_id,))
        if not rows or len(rows) < 2:
            return None
        months = [(r[0][:7], float(r[1] or 0)) for r in rows]
        return {'months': months, 'total': sum(m[1] for m in months)}
    except Exception:
        return None


def _collect_meta_x_spotify(db, artist_id, from_date, to_date):
    """Dépense Meta vs streams Spotify (base 100) sur la fenêtre de la dernière campagne."""
    if artist_id is None:
        return None
    try:
        camp = db.fetch_query(
            """SELECT campaign_name, MIN(day_date), MAX(day_date)
               FROM meta_insights_performance_day
               WHERE artist_id = %s AND day_date BETWEEN %s AND %s
               GROUP BY campaign_name ORDER BY MAX(day_date) DESC LIMIT 1""",
            (artist_id, from_date, to_date))
        if not camp:
            return None
        name, c_from, c_to = camp[0]
        meta = db.fetch_query(
            """SELECT day_date::text, SUM(spend), SUM(results),
                      SUM(spend) / NULLIF(SUM(results), 0)
               FROM meta_insights_performance_day
               WHERE artist_id = %s AND campaign_name = %s AND day_date BETWEEN %s AND %s
               GROUP BY day_date ORDER BY day_date""",
            (artist_id, name, c_from, c_to))
        streams = db.fetch_query(
            """SELECT date::text, SUM(streams) FROM s4a_song_timeline
               WHERE artist_id = %s AND song NOT ILIKE %s AND date BETWEEN %s AND %s
               GROUP BY date ORDER BY date""",
            (artist_id, f"%{ARTIST_NAME_FILTER}%", c_from, c_to))
        pop = db.fetch_query(
            f"""SELECT date::text, MAX(popularity) FROM track_popularity_history
                WHERE {canonical_song_sql('track_name')} NOT ILIKE %s
                  AND artist_id = %s AND date BETWEEN %s AND %s
                GROUP BY date ORDER BY date""",
            (f"%{ARTIST_NAME_FILTER}%", artist_id, c_from, c_to))
        sp = {r[0]: float(r[1] or 0) for r in (meta or [])}
        res = {r[0]: int(r[2] or 0) for r in (meta or [])}
        cpr = {r[0]: float(r[3] or 0) for r in (meta or [])}
        stq = {r[0]: int(r[1] or 0) for r in (streams or [])}
        pp = {r[0]: int(r[1] or 0) for r in (pop or [])}
        dates = sorted(set(sp) | set(stq) | set(pp))
        if len(dates) < 2:
            return None
        idx = {d: i for i, d in enumerate(dates)}
        ser = lambda m: [(idx[d], m.get(d)) for d in dates]  # noqa: E731
        return {
            'campaign': name,
            'spend':   ser(sp), 'results': ser(res), 'cpr': ser(cpr),
            'streams': ser(stq), 'popularity': ser(pp),
        }
    except Exception:
        return None


def _has_wrapped(db, artist_id):
    try:
        r = db.fetch_query(
            "SELECT 1 FROM artist_wrapped WHERE artist_id = %s LIMIT 1", (artist_id,))
        return bool(r)
    except Exception:
        return False


_CRED_PLATFORMS = [("spotify", "🎵 Spotify"), ("youtube", "🎬 YouTube"),
                   ("soundcloud", "☁️ SoundCloud"), ("meta", "📱 Meta / Instagram")]


def _collect_credentials_status(db, artist_id):
    """Per-platform 'configured?' — per-tenant artist_credentials OR app-level
    (config.yaml/.env), mirroring the green status shown in the app."""
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            "SELECT platform FROM artist_credentials WHERE artist_id = %s", (artist_id,))
        have = {r[0] for r in (rows or [])}
    except Exception:
        return None
    try:
        from src.dashboard.views.credentials._core import app_level_configured
    except Exception:
        def app_level_configured(_):  # noqa: E731 — graceful fallback
            return False
    return [(label, (key in have) or app_level_configured(key))
            for key, label in _CRED_PLATFORMS]


def _collect_mapping(db, artist_id):
    """Campaign↔track mapping rows for the artist."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            "SELECT campaign_name, track_name FROM campaign_track_mapping "
            "WHERE artist_id = %s ORDER BY campaign_name", (artist_id,))
        return [(r[0], r[1]) for r in rows] if rows else []
    except Exception:
        return []


def _collect_youtube_history(db, artist_id):
    """Daily channel snapshots: (date, subscribers, cumulative views)."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            "SELECT date(collected_at), MAX(subscriber_count), MAX(view_count) "
            "FROM youtube_channel_history WHERE artist_id = %s GROUP BY 1 ORDER BY 1",
            (artist_id,))
        return [(r[0], int(r[1] or 0), int(r[2] or 0)) for r in rows] if rows else []
    except Exception:
        return []


def _collect_s4a_audience(db, artist_id):
    """s4a_audience listeners/followers over time."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            "SELECT date, listeners, followers FROM s4a_audience "
            "WHERE artist_id = %s ORDER BY date", (artist_id,))
        return [(r[0], r[1], r[2]) for r in rows] if rows else []
    except Exception:
        return []


def _collect_s4a_daily(db, artist_id, from_date, to_date):
    """Deduped daily streams over the period (feeds cumulative + timeline charts)."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            """SELECT date, SUM(daily_max) FROM (
                   SELECT date, song, MAX(streams) AS daily_max FROM s4a_song_timeline
                   WHERE artist_id = %s AND song NOT ILIKE %s AND date BETWEEN %s AND %s
                   GROUP BY date, song) t
               GROUP BY date ORDER BY date""",
            (artist_id, f"%{ARTIST_NAME_FILTER}%", from_date, to_date))
        return [(r[0], int(r[1] or 0)) for r in rows] if rows else []
    except Exception:
        return []


def _release_date(db, artist_id, song, fallback):
    """Real release date from tracks (canonical match), else fallback."""
    try:
        rr = db.fetch_query(
            f"SELECT release_date FROM tracks WHERE {canonical_song_sql('track_name')} = %s "
            f"AND saas_artist_id = %s AND release_date IS NOT NULL LIMIT 1",
            (song, artist_id))
        if rr and rr[0][0]:
            return rr[0][0]
    except Exception:
        pass
    return fallback


def _collect_j28(db, artist_id, song):
    """Cumulative streams J0..J+28 since release for one song → [(day_index, cumul)]."""
    if artist_id is None or not song:
        return []
    try:
        rows = db.fetch_query(
            "SELECT date, streams FROM s4a_song_timeline "
            "WHERE song = %s AND artist_id = %s AND date IS NOT NULL ORDER BY date ASC",
            (song, artist_id))
    except Exception:
        return []
    rows = [(r[0], int(r[1] or 0)) for r in (rows or []) if r[1] is not None]
    if len(rows) < 2:
        return []
    rd = _release_date(db, artist_id, song, rows[0][0])
    end = rd + timedelta(days=28)
    cumul, acc = [], 0
    for d, v in rows:
        if d < rd or d > end:
            continue
        acc += v
        cumul.append(((d - rd).days, acc))
    return cumul


def _collect_song_timeline(db, artist_id, song, from_date, to_date):
    """Single song's daily streams over the period (latest snapshot per day)."""
    if artist_id is None or not song:
        return []
    try:
        rows = db.fetch_query(
            """SELECT date, streams FROM (
                   SELECT DISTINCT ON (date) date, streams FROM s4a_song_timeline
                   WHERE artist_id = %s AND song = %s AND date BETWEEN %s AND %s
                   ORDER BY date, collected_at DESC) t ORDER BY date""",
            (artist_id, song, from_date, to_date))
        return [(r[0], int(r[1] or 0)) for r in rows] if rows else []
    except Exception:
        return []


def _collect_apple_daily(db, artist_id, single_song, from_date, to_date):
    """Daily streams + shazams (LAG diff over apple_songs_history), track-scoped."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            """SELECT date, song_name,
                      plays - LAG(plays) OVER (PARTITION BY song_name ORDER BY date),
                      shazam_count - LAG(shazam_count) OVER (PARTITION BY song_name ORDER BY date)
               FROM apple_songs_history WHERE artist_id = %s AND date BETWEEN %s AND %s
               ORDER BY song_name, date""",
            (artist_id, from_date, to_date))
    except Exception:
        return []
    agg = {}
    for d, name, ds, dsh in (rows or []):
        if ds is None or (single_song and not track_title_matches(single_song, name)):
            continue
        a = agg.setdefault(d, [0, 0])
        a[0] += max(0, int(ds or 0))
        a[1] += max(0, int(dsh or 0))
    return [(d, v[0], v[1]) for d, v in sorted(agg.items())]


def _collect_apple_timeline(db, artist_id, single_song, from_date, to_date):
    """Cumulative plays + shazams per snapshot date (apple_songs_history), track-scoped."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            """SELECT date, song_name, plays, shazam_count FROM apple_songs_history
               WHERE artist_id = %s AND date BETWEEN %s AND %s ORDER BY date""",
            (artist_id, from_date, to_date))
    except Exception:
        return []
    agg = {}
    for d, name, plays, shz in (rows or []):
        if single_song and not track_title_matches(single_song, name):
            continue
        a = agg.setdefault(d, [0, 0])
        a[0] += int(plays or 0)
        a[1] += int(shz or 0)
    return [(d, v[0], v[1]) for d, v in sorted(agg.items())]


def _collect_sc_series(db, artist_id, single_song, from_date, to_date):
    """SoundCloud daily totals (plays/likes/reposts/comments), track-scoped."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            """SELECT collected_at::date, title, playback_count, likes_count,
                      reposts_count, comment_count FROM soundcloud_tracks_daily
               WHERE artist_id = %s AND collected_at::date BETWEEN %s AND %s
               ORDER BY collected_at""",
            (artist_id, from_date, to_date))
    except Exception:
        return []
    agg = {}
    for d, title, pb, lk, rp, cm in (rows or []):
        if not pb:  # skip anomalous zero-playback snapshots (collection glitch → dip to 0)
            continue
        if single_song and not track_title_matches(single_song, title):
            continue
        a = agg.setdefault(d, [0, 0, 0, 0])
        a[0] += int(pb or 0); a[1] += int(lk or 0)
        a[2] += int(rp or 0); a[3] += int(cm or 0)
    return [(d, *v) for d, v in sorted(agg.items())]


def _collect_ig_monthly(db, artist_id, from_date, to_date):
    """Instagram monthly engagement + rate (vs latest followers) → [(YYYY-MM,l,c,rate)]."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            """SELECT date_trunc('month', timestamp)::date, SUM(like_count),
                      SUM(comments_count), COUNT(*) FROM instagram_media
               WHERE artist_id = %s AND timestamp BETWEEN %s AND %s
               GROUP BY 1 ORDER BY 1""",
            (artist_id, from_date, to_date))
        fr = db.fetch_query(
            "SELECT followers_count FROM instagram_daily_stats WHERE artist_id = %s "
            "ORDER BY collected_at DESC LIMIT 1", (artist_id,))
        followers = int(fr[0][0]) if fr and fr[0][0] else 0
    except Exception:
        return []
    out = []
    for m, likes, comments, posts in (rows or []):
        rate = ((int(likes or 0) + int(comments or 0)) / posts / followers * 100
                if posts and followers else 0)
        out.append((str(m)[:7], int(likes or 0), int(comments or 0), round(rate, 2)))
    return out


def _collect_meta_funnel(db, artist_id, from_date, to_date):
    """Funnel counts (Impressions→Reach→Résultats→Conversions) from perf_day."""
    if artist_id is None:
        return []
    try:
        r = db.fetch_query(
            """SELECT COALESCE(SUM(impressions),0), COALESCE(SUM(reach),0),
                      COALESCE(SUM(results),0), COALESCE(SUM(custom_conversions),0)
               FROM meta_insights_performance_day
               WHERE artist_id = %s AND day_date BETWEEN %s AND %s""",
            (artist_id, from_date, to_date))
    except Exception:
        return []
    if not r:
        return []
    imp, reach, res, conv = (int(r[0][i] or 0) for i in range(4))
    return [("Impressions", imp), ("Reach", reach), ("Résultats", res),
            ("Conversions Spotify", conv)]


def _collect_meta_daily(db, artist_id, from_date, to_date):
    """Daily budget + results + CPR (=spend/results) from perf_day."""
    if artist_id is None:
        return []
    try:
        rows = db.fetch_query(
            """SELECT day_date, SUM(spend), SUM(results)
               FROM meta_insights_performance_day
               WHERE artist_id = %s AND day_date BETWEEN %s AND %s
               GROUP BY day_date ORDER BY day_date""",
            (artist_id, from_date, to_date))
    except Exception:
        return []
    out = []
    for d, spend, res in (rows or []):
        sp, rs = float(spend or 0), int(res or 0)
        out.append((d, sp, rs, (sp / rs if rs else 0)))
    return out


def _collect_ml_explain(db, artist_id, tracks):
    """[(track, features_json)] for SHAP/cursors — report tracks capped at 5."""
    out = []
    try:
        from src.dashboard.views.trigger_algo._common import _load_ml_pred
    except Exception:
        return out
    for t in (tracks or [])[:5]:
        try:
            pred = _load_ml_pred(db, t, artist_id)
        except Exception:
            pred = None
        if pred and pred.get('features_json'):
            out.append((t, pred['features_json']))
    return out


def _collect_score20(db, artist_id, sel):
    """Score /20 rows for the report tracks (catalogue-relative). Reuses the view's
    pure helper. → [(song, score_20, dw, rr, radio)]."""
    try:
        from src.dashboard.views.trigger_algo._common import _load_scored_tracks
        df = _load_scored_tracks(db, artist_id)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    if sel:
        df = df[df['song'].isin(sel)]
    if df.empty:
        return []
    df = df.sort_values('score_20', ascending=False)
    return [
        (r['song'], float(r['score_20'] or 0), float(r['dw_probability'] or 0),
         float(r['rr_probability'] or 0), float(r['radio_probability'] or 0))
        for _, r in df.iterrows()
    ]


def _collect_pi_gate(db, artist_id, song):
    """Load PI→trigger threshold tables (JSON) + the focus song's PI bracket."""
    try:
        import json
        from src.utils.ml_inference import _resolve_path
        with open(_resolve_path("threshold_tables.json"), encoding="utf-8") as f:
            tables = json.load(f)
    except Exception:
        return None, None
    here = None
    try:
        r = db.fetch_query(
            "SELECT pi_forecast_7d FROM ml_song_predictions WHERE artist_id = %s AND song = %s "
            "ORDER BY prediction_date DESC LIMIT 1", (artist_id, song))
        pi = r[0][0] if r and r[0][0] is not None else None
        if pi is not None:
            for lo, hi, lbl in [(0, 10, "0-10"), (11, 20, "11-20"), (21, 30, "21-30"),
                                (31, 40, "31-40"), (41, 50, "41-50"), (51, 10_000, "50+")]:
                if lo <= pi <= hi:
                    here = lbl
                    break
    except Exception:
        pass
    return tables, here
