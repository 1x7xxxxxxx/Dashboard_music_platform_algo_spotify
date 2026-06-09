"""Génération de rapports PDF artiste via WeasyPrint."""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from dateutil.relativedelta import relativedelta

_ASSETS = Path(__file__).resolve().parent.parent / "assets"


def _logo_svg() -> str:
    """Inline the light wordmark SVG for the cover (empty string if missing)."""
    try:
        return (_ASSETS / "logo_horizontal_light.svg").read_text(encoding="utf-8")
    except Exception:
        return ""

# WeasyPrint's base fonts have no emoji glyphs (they render as tofu boxes), so we
# strip emoji from the final HTML. The matplotlib charts carry no emoji.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF✀-➿️⭐⬆☁❤]+"
)

from src.utils.track_matching import track_title_matches, canonical_song_sql
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
    get_total_streams_s4a, get_total_views_youtube,
    get_total_plays_soundcloud, get_total_plays_apple,
    get_spotify_popularity, get_instagram_followers, get_soundcloud_likes,
    get_roi_data,
    ARTIST_NAME_FILTER,
)

# Sections du rapport — ordre = parcours de l'app (_NAV_SECTIONS).
# Sections that mirror Premium-only views (ML prediction/explainability, revenue
# forecast, Meta breakdowns, Meta×Spotify). Free users can export the PDF but NOT
# these sections — gated in views/export_pdf.py (UI lock + generation strip).
PREMIUM_SECTIONS = frozenset({
    'songs', 'ml_explain', 'revenue_forecast', 'meta_breakdowns', 'meta_x_spotify',
})

ALL_SECTIONS = {
    'overview':           "🏠 Vue d'ensemble",
    'data_setup':         '📁 Connexions & mapping',
    'freshness':          '📡 Fraîcheur des sources',
    'streams':            '🎵 S4A — évolution',
    's4a_songs':          '🎵 S4A — chansons',
    'meta_x_spotify':     '🔗 Meta × Spotify',
    'apple':              '🍎 Apple Music',
    'youtube':            '🎬 YouTube',
    'soundcloud_detail':  '☁️ SoundCloud',
    'instagram':          '📸 Instagram',
    'hypeddit':           '📣 Hypeddit',
    'songs':              '🔮 Prédiction algos',
    'ml_explain':         '🔬 Explainabilité (SHAP)',
    'meta':               '📱 Meta Ads',
    'meta_breakdowns':    '🌍 Meta — Répartitions',
    'roi':                '💹 ROI Breakeven',
    'revenue_forecast':   '📈 Prévisions revenus',
}

# ─── CSS ─────────────────────────────────────────────────────────────────────

_CSS = """
@page { size: A4; margin: 15mm 14mm 16mm 14mm;
        @bottom-center { content: "streaMLytics  ·  Page " counter(page) " / " counter(pages);
                         font-size: 7.5pt; color: #b8b8b8; } }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
       font-size: 10.5pt; color: #1a1a2e; background: #fff; }
.content { padding: 0 2mm; }

/* ── Cover banner (top of page 1, NOT full page — completeness + freshness follow) ── */
.cover { padding: 22px 26px 20px 26px; border-radius: 14px; margin-bottom: 16px;
         background: linear-gradient(150deg, #191414 0%, #0d3b22 60%, #1DB954 135%);
         color: #fff; page-break-inside: avoid; }
.cover .cov-logo { margin-bottom: 12px; }
.cover .cov-logo svg { width: 260px; height: auto; }
.cover .eyebrow { font-size: 10pt; letter-spacing: 3px; text-transform: uppercase;
                  color: #1DB954; font-weight: 700; }
.cover h1 { font-size: 26pt; line-height: 1.05; margin: 4px 0 2px 0; color: #fff; border: 0; }
.cover .meta { font-size: 12pt; color: #cfe9d8; margin-top: 14px; }
.cover .cov-kpis { display: flex; gap: 9px; margin-top: 46mm; }
.cover .cov-kpi { flex: 1 1 0; min-width: 0; background: rgba(255,255,255,0.08);
                  border: 1px solid rgba(255,255,255,0.18); border-radius: 12px;
                  padding: 14px 8px; text-align: center; }
.cover .cov-kpi .v { font-size: 19pt; font-weight: 800; color: #fff; }
.cover .cov-kpi .l { font-size: 8pt; color: #bfe8cd; margin-top: 4px;
                     text-transform: uppercase; letter-spacing: 1px; }

/* ── Sections ── */
h1 { font-size: 18pt; color: #1DB954; }
h2 { font-size: 14pt; color: #11261a; margin: 26px 0 12px 0; padding-bottom: 6px;
     border-bottom: 2px solid #1DB954; page-break-after: avoid; }
h3 { font-size: 10.5pt; color: #444; margin: 14px 0 6px 0; }
.section { page-break-inside: avoid; margin-bottom: 8px; }
.subtitle { color: #666; font-size: 9pt; margin-bottom: 18px; }
.lead { background: #f0faf3; border-left: 4px solid #1DB954; border-radius: 6px;
        padding: 10px 14px; font-size: 9.5pt; color: #2a4a38; margin: 4px 0 14px 0; }

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; margin: 6px 0 12px 0; }
th { background: #11261a; color: #fff; font-size: 8.5pt; padding: 7px 10px;
     text-align: left; text-transform: uppercase; letter-spacing: 0.5px; }
td { padding: 6px 10px; font-size: 9.5pt; border-bottom: 1px solid #eee; }
tr:nth-child(even) td { background: #f7faf8; }
table.compact th, table.compact td { padding: 2.5px 8px; font-size: 8pt; }
.status-row { display: flex; gap: 16px; page-break-inside: avoid; }
.status-col { flex: 1; min-width: 0; }
.status-col h3 { margin: 2px 0 4px 0; }

/* ── Badges & cards ── */
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 8.5pt; font-weight: 600; color: #fff; }
.green { background: #1DB954; } .orange { background: #FFA500; }
.red { background: #FF4444; } .gray { background: #888; }
.kpi-grid { display: flex; gap: 9px; margin: 6px 0 12px 0; }
.kpi-card { flex: 1 1 0; min-width: 0; border: 1px solid #e6e6e6; background: #fff;
            border-radius: 10px; padding: 12px 8px; text-align: center;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.kpi-val { font-size: 14.5pt; font-weight: 800; color: #1DB954; }
.kpi-lbl { font-size: 8pt; color: #777; margin-top: 3px; }
.roi-card { background: #f0faf3; border: 1px solid #1DB954; border-radius: 10px;
            padding: 14px 18px; margin-bottom: 12px; }
.roi-row { display: flex; gap: 32px; } .roi-item { flex: 1; }

/* ── Charts ── */
.chart { width: 100%; margin: 8px 0 14px 0; page-break-inside: avoid; }
.chart img { width: 100%; border: 1px solid #eee; border-radius: 8px; }
.chart-row { display: flex; gap: 14px; page-break-inside: avoid; }
.chart-row .chart { flex: 1; }

/* ── Song / spotlight ── */
.song-block { border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; }
.song-title { font-weight: 700; font-size: 11pt; color: #1DB954; margin-bottom: 8px; }
.spotlight { background: #11261a; color: #fff; border-radius: 12px; padding: 18px 22px;
             margin: 6px 0 14px 0; page-break-inside: avoid; }
.spotlight h2 { color: #fff; border-color: #1DB954; margin-top: 0; }
.spotlight .name { font-size: 16pt; font-weight: 800; color: #1DB954; }
.prob-bar-wrap { background: #eee; border-radius: 4px; height: 10px; width: 100%; margin: 2px 0 6px 0; }
.prob-bar { background: #1DB954; border-radius: 4px; height: 10px; }
.no-data { color: #aaa; font-style: italic; font-size: 9pt; }
.footer { margin-top: 30px; font-size: 7.5pt; color: #aaa; text-align: center;
          border-top: 1px solid #eee; padding-top: 10px; }
"""

# ─── Helpers DB ───────────────────────────────────────────────────────────────

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


# ─── Collecte des données ─────────────────────────────────────────────────────

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


# Allowlist (table, dimension column) — fixed mapping, never user input (Rule 8).
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


# Per-tenant credential platforms (mirror of credentials/_registry.PLATFORMS).
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


def collect_report_data(db, artist_id, from_date, to_date, songs=None, s4a_songs_filter=None):
    """
    Retourne un dict avec toutes les métriques nécessaires au rapport.
    songs : liste de noms de chansons pour la section focus (None = pas de section songs).
    """
    now = datetime.now()
    months = max(1, round((to_date - from_date).days / 30))

    freshness = get_source_freshness(db, artist_id)
    s4a   = get_total_streams_s4a(db, artist_id)
    yt    = get_total_views_youtube(db, artist_id)
    sc    = get_total_plays_soundcloud(db, artist_id)
    apple = get_total_plays_apple(db, artist_id)
    pop   = get_spotify_popularity(db, artist_id)
    ig    = get_instagram_followers(db, artist_id)
    likes = get_soundcloud_likes(db, artist_id)
    # Ads/revenue family is ALWAYS all-time (campaign/revenue history, not a streaming
    # window) — a recent period would wrongly show empty (data ends 2024). The streaming
    # collectors below keep the user-selected period.
    _ad_from = date(2015, 1, 1)
    roi   = get_roi_data(db, artist_id, _ad_from, to_date)

    # Selected report tracks. N==1 → per-song views; N>=2 → top-N filtered; N==0 → catalogue.
    _sel = list(dict.fromkeys(s4a_songs_filter or []))
    _n = len(_sel)
    _single_song = _sel[0] if _n == 1 else None
    try:
        _r = db.fetch_query(
            "SELECT COUNT(DISTINCT song) FROM s4a_song_timeline "
            "WHERE artist_id = %s AND song NOT ILIKE %s",
            (artist_id, f"%{ARTIST_NAME_FILTER}%"))
        n_catalog = int(_r[0][0]) if _r else 0
    except Exception:
        n_catalog = 0

    songs_data       = _collect_songs_focus(db, artist_id, songs, from_date, to_date) if songs else []
    s4a_top_songs    = _collect_s4a_top_songs(db, artist_id, from_date, to_date, songs_filter=s4a_songs_filter)
    youtube_data     = _collect_youtube(db, artist_id, single_song=_single_song)
    instagram_data   = _collect_instagram(db, artist_id, from_date, to_date)
    meta_data        = _collect_meta(db, artist_id, _ad_from, to_date)
    sc_tracks        = _collect_soundcloud_tracks(db, artist_id, single_song=_single_song)
    apple_data       = _collect_apple(db, artist_id, selected_songs=_sel)
    hypeddit_data    = _collect_hypeddit(db, artist_id, _ad_from, to_date)
    hypeddit_camps   = _collect_hypeddit_campaigns(db, artist_id, _ad_from, to_date)
    breakdowns       = _collect_meta_breakdowns(db, artist_id)
    revenue_fc       = _collect_revenue_forecast(db, artist_id)
    meta_x_spotify   = _collect_meta_x_spotify(db, artist_id, _ad_from, to_date)
    meta_funnel_d    = _collect_meta_funnel(db, artist_id, _ad_from, to_date)
    meta_daily_d     = _collect_meta_daily(db, artist_id, _ad_from, to_date)
    creds_status     = _collect_credentials_status(db, artist_id)
    mapping_rows     = _collect_mapping(db, artist_id)
    yt_history       = _collect_youtube_history(db, artist_id)
    s4a_audience_s   = _collect_s4a_audience(db, artist_id)
    s4a_daily        = _collect_s4a_daily(db, artist_id, from_date, to_date)
    song_tl = (_collect_song_timeline(db, artist_id, _single_song, from_date, to_date)
               if _single_song else [])
    apple_ts         = _collect_apple_timeline(db, artist_id, _single_song, from_date, to_date)
    sc_series        = _collect_sc_series(db, artist_id, _single_song, from_date, to_date)
    ig_monthly       = _collect_ig_monthly(db, artist_id, from_date, to_date)

    # Latest release (timeline '_' form) + embedded chart images (base64 PNG).
    latest_release = _latest_release(db, artist_id)
    _focus_song = _single_song or latest_release
    j28 = _collect_j28(db, artist_id, _focus_song)
    pi_tables, pi_here = _collect_pi_gate(db, artist_id, _focus_song)
    pl_windows = _collect_playlist_adds_windows(db, artist_id, _focus_song)
    score20 = _collect_score20(db, artist_id, _sel)
    _explain_tracks = _sel or ([_focus_song] if _focus_song else [])
    ml_explain = _collect_ml_explain(db, artist_id, _explain_tracks)
    from src.dashboard.utils import pdf_charts
    streams_dict = {'s4a': s4a, 'youtube': yt, 'soundcloud': sc, 'apple': apple}
    charts = {
        'streams':  pdf_charts.streams_timeline(db, artist_id, from_date, to_date),
        'platform': pdf_charts.platform_breakdown(streams_dict),
        'ml':       pdf_charts.ml_probabilities(db, artist_id, latest_release) if latest_release else None,
        'j28':      pdf_charts.j28_trajectory(j28),
        'roi':      pdf_charts.roi_breakeven(roi),
        's4a_top':  pdf_charts.top_songs_bar(s4a_top_songs, "Top chansons Spotify (période)"),
        'youtube':  pdf_charts.youtube_top_videos_bar(youtube_data['videos']) if youtube_data else None,
        'soundcloud': pdf_charts.soundcloud_top_bar(sc_tracks),
        'apple':    pdf_charts.top_songs_bar(apple_data['top_songs'], "Top chansons Apple Music")
                    if apple_data else None,
        'instagram': pdf_charts.instagram_followers_line(instagram_data['history'])
                     if instagram_data else None,
        'meta':     pdf_charts.meta_campaigns_bar(meta_data['campaigns']) if meta_data else None,
        'hypeddit': pdf_charts.hypeddit_combo(hypeddit_data['series']) if hypeddit_data else None,
        'bd_country': pdf_charts.meta_breakdown_bars(
            breakdowns['country'], "Meta — dépense par pays") if breakdowns else None,
        'bd_placement': pdf_charts.meta_breakdown_bars(
            breakdowns['placement'], "Meta — dépense par placement") if breakdowns else None,
        'bd_age': pdf_charts.meta_breakdown_bars(
            breakdowns['age'], "Meta — dépense par âge") if breakdowns else None,
        'revenue_fc': pdf_charts.revenue_forecast_chart(revenue_fc['months']) if revenue_fc else None,
        'mxs': pdf_charts.indexed_lines(
            {'Budget Meta': meta_x_spotify['spend'], 'Résultats': meta_x_spotify['results'],
             'CPR': meta_x_spotify['cpr'], 'Streams Spotify': meta_x_spotify['streams'],
             'Popularité': meta_x_spotify['popularity']},
            f"Meta × Spotify — {meta_x_spotify['campaign']} (base 100)") if meta_x_spotify else None,
        'hypeddit_camps': pdf_charts.hypeddit_campaigns_bar(hypeddit_camps),
        'playlist_adds': pdf_charts.playlist_adds_bars(pl_windows),
        'meta_funnel': pdf_charts.meta_funnel(meta_funnel_d),
        'meta_daily': pdf_charts.meta_daily(meta_daily_d),
        'pi_gate':    pdf_charts.pi_gate(pi_tables, pi_here),
        'apple_daily': pdf_charts.apple_timeline(apple_ts),
        'sc_multi': pdf_charts.sc_multiaxis(sc_series),
        'ig_engagement': pdf_charts.ig_engagement(ig_monthly),
        's4a_cumulative': pdf_charts.s4a_cumulative(s4a_daily),
        's4a_audience': pdf_charts.s4a_audience_evolution(s4a_audience_s),
        'yt_growth': pdf_charts.youtube_channel_growth(yt_history),
        'song_tl': pdf_charts.song_timeline(song_tl, _single_song) if _single_song else None,
    }

    return {
        'latest_release':  latest_release,
        'charts':          charts,
        'generated_at':    now,
        'period_months':   months,
        'from_date':       from_date,
        'to_date':         to_date,
        'freshness':       freshness,
        'streams':         {'s4a': s4a, 'youtube': yt, 'soundcloud': sc, 'apple': apple,
                            'total': s4a + yt + sc + apple},
        'spotify_popularity': pop,
        'instagram':       ig,
        'soundcloud_likes': likes,
        'roi':             roi,
        'songs_data':      songs_data,
        's4a_top_songs':   s4a_top_songs,
        'youtube_data':    youtube_data,
        'instagram_data':  instagram_data,
        'meta_data':       meta_data,
        'sc_tracks':       sc_tracks,
        'apple_data':      apple_data,
        'hypeddit_data':   hypeddit_data,
        'breakdowns':      breakdowns,
        'revenue_fc':      revenue_fc,
        'meta_x_spotify':  meta_x_spotify,
        'has_wrapped':     _has_wrapped(db, artist_id),
        'creds_status':    creds_status,
        'mapping_rows':    mapping_rows,
        'single_song':     _single_song,
        'report_n':        _n,
        'n_catalog':       n_catalog,
        'report_tracks':   _sel,
        'pl_windows':      pl_windows,
        'focus_song':      _focus_song,
        'score20':         score20,
        'ml_explain':      ml_explain,
        'ml_explain_truncated': _n > 5,
    }


# ─── Rendu HTML ──────────────────────────────────────────────────────────────

def _badge(emoji, label):
    css = {'🟢': 'green', '🟠': 'orange', '🔴': 'red'}.get(emoji, 'gray')
    return f'<span class="badge {css}">{emoji} {label}</span>'


# ── HTML primitives shared by the platform renderers (exact-string, move-only) ──

def _html_table(headers, rows_html):
    """`<table>` with a `<thead>` row of `headers` and the given `<tbody>` rows."""
    th = "".join(f"<th>{h}</th>" for h in headers)
    return (f'<table><thead><tr>{th}</tr></thead>'
            f'<tbody>{rows_html}</tbody></table>')


def _kpi_card(val_html, label, *, card_style="", val_style=""):
    """A single `kpi-card` (value + label), with optional card/value inline styles."""
    cs = f' style="{card_style}"' if card_style else ""
    vs = f' style="{val_style}"' if val_style else ""
    return (f'<div class="kpi-card"{cs}><div class="kpi-val"{vs}>{val_html}</div>'
            f'<div class="kpi-lbl">{label}</div></div>')


def _kpi_grid(cards_html):
    return f'<div class="kpi-grid">{cards_html}</div>'


def _render_freshness(freshness):
    rows = []
    for label, info in freshness.items():
        emoji, _, age_label = freshness_status(info['last_dt'])
        rows.append(
            f"<tr><td>{info['icon']} {label}</td>"
            f"<td>{_badge(emoji, age_label)}</td></tr>"
        )
    return f"""<table class="compact">
      <thead><tr><th>Source</th><th>Dernière collecte</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>"""


def _render_streams(streams):
    items = [
        ("🎵 Spotify S4A", streams['s4a']),
        ("🎬 YouTube",      streams['youtube']),
        ("☁️ SoundCloud",   streams['soundcloud']),
        ("🍎 Apple Music",  streams['apple']),
    ]
    total_card = _kpi_card(
        f'{streams["total"]:,}', "🎧 Total toutes plateformes",
        card_style="border-color:#1DB954; background:#f0faf3;",
        val_style="font-size:22pt;",
    )
    cards = "".join(_kpi_card(f'{v:,}', lbl) for lbl, v in items)
    return _kpi_grid(total_card + cards)


def _render_roi(roi, from_date, to_date):
    rev = float(roi.get('revenue_eur') or 0)
    spend = float(roi.get('meta_spend') or 0)
    net = rev - spend
    # TRUE ROI = (gain - cost) / cost. The shared helper's roi_pct is rev/spend
    # (a recovery ratio), which mislabels a deficit as "+6.9%". Compute it right here.
    roi_true = (net / spend * 100) if spend > 0 else None
    roi_val = f"{roi_true:+.1f} %" if roi_true is not None else "—"
    net_color = "#1DB954" if net >= 0 else "#FF4444"
    status = "✅ Rentable" if net >= 0 else "⚠️ Déficitaire"
    return f"""
    <div class="roi-card">
      <p style="font-size:8.5pt;color:#555;margin-bottom:10px;">Depuis le début (tout l'historique)</p>
      <div class="roi-row">
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;">{rev:,.2f} €</div>
          <div class="kpi-lbl">💰 Revenus iMusician</div>
        </div>
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;color:#FF4444;">{spend:,.2f} €</div>
          <div class="kpi-lbl">📱 Dépenses Meta Ads</div>
        </div>
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;color:{net_color};">{net:,.2f} €</div>
          <div class="kpi-lbl">Net (revenus − dépenses)</div>
        </div>
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;color:{net_color};">{roi_val}</div>
          <div class="kpi-lbl">📊 ROI — {status}</div>
        </div>
      </div>
    </div>"""


def _prob_bar(pct):
    """Barre de progression HTML pour une probabilité (0–1)."""
    w = int(min(max(pct * 100, 0), 100))
    color = "#1DB954" if pct >= 0.5 else ("#FFA500" if pct >= 0.3 else "#FF4444")
    return (
        f'<div class="prob-bar-wrap">'
        f'<div class="prob-bar" style="width:{w}%;background:{color};"></div></div>'
        f'<span style="font-size:8pt;color:#555;">{pct*100:.0f}%</span>'
    )


def _render_songs_focus(songs_data):
    if not songs_data:
        return '<p class="no-data">Aucune chanson sélectionnée.</p>'
    parts = []
    for s in songs_data:
        ml = s['ml']
        if ml:
            ml_html = f"""
            <table style="width:100%;margin-top:8px;">
              <thead><tr>
                <th>DW Playlist</th><th>Release Radar</th><th>Radio</th>
                <th>Forecast DW 7j</th><th>Forecast RR 7j</th>
              </tr></thead>
              <tbody><tr>
                <td>{_prob_bar(ml['dw_prob'])}</td>
                <td>{_prob_bar(ml['rr_prob'])}</td>
                <td>{_prob_bar(ml['radio_prob'])}</td>
                <td><b>{int(ml['dw_forecast']):,}</b> streams</td>
                <td><b>{int(ml['rr_forecast']):,}</b> streams</td>
              </tr></tbody>
            </table>
            <p style="font-size:7.5pt;color:#aaa;margin-top:4px;">
              Prédiction du {ml['prediction_date']}
            </p>"""
        else:
            ml_html = '<p class="no-data" style="margin-top:6px;">Pas de prédiction ML disponible.</p>'

        parts.append(f"""
        <div class="song-block">
          <div class="song-title">🎵 {s['song']}</div>
          <table style="width:auto;margin-bottom:0;">
            <tr>
              <td style="padding:3px 16px 3px 0;border:none;">
                Streams (période) : <b>{s['total_streams']:,}</b>
              </td>
              <td style="padding:3px 0;border:none;">
                Streams 7 derniers jours : <b>{s['last7d_streams']:,}</b>
              </td>
            </tr>
          </table>
          {ml_html}
        </div>""")
    return "\n".join(parts)


def _render_s4a_top_songs(songs):
    if not songs:
        return '<p class="no-data">Aucune donnée S4A disponible.</p>'
    rows = "".join(
        f"<tr><td>{s[0]}</td><td>{s[1]:,}</td><td>{s[2]:,}</td></tr>"
        for s in songs[:5]
    )
    return _html_table(
        ['Chanson', 'Streams (période)', 'Streams 7 derniers jours'], rows)


def _render_youtube(yt):
    if not yt:
        return '<p class="no-data">Aucune donnée YouTube disponible.</p>'
    # KPI header only — the growth + top-videos charts carry the detail (no table).
    return _kpi_grid(
        _kpi_card(f'{yt["subscriber_count"]:,}', "Abonnés")
        + _kpi_card(f'{yt["total_views"]:,}', "Vues totales (chaîne)")
    )


def _render_instagram(ig):
    if not ig:
        return '<p class="no-data">Aucune donnée Instagram disponible.</p>'
    summary = _kpi_grid(
        _kpi_card(f'{ig["followers"]:,}', f'@{ig["username"]} — Abonnés')
        + _kpi_card(f'{ig["media_count"]:,}', "Publications")
    )
    # History is shown by the followers line chart above — KPIs only here.
    return summary


def _render_meta(meta):
    if not meta or not meta['campaigns']:
        return '<p class="no-data">Aucune donnée Meta Ads disponible.</p>'
    summary = _kpi_grid(
        _kpi_card(f'{meta["total_spend"]:,.2f} €', "Dépenses totales",
                  val_style="color:#FF4444;")
        + _kpi_card(f'{meta["total_results"]:,}', "Résultats totaux")
    )
    rows = "".join(
        f"<tr><td>{c[0]}</td><td>{c[1]:,.2f} €</td><td>{c[2]:,}</td>"
        f"<td>{c[3]:,}</td><td>{c[4]:,}</td><td>{c[5]:,.2f} €</td></tr>"
        for c in meta['campaigns'][:5]
    )
    table = _html_table(
        ['Campagne', 'Dépenses', 'Résultats', 'Impressions', 'Reach', 'CPR'], rows)
    return summary + table


def _render_soundcloud_tracks(tracks):
    if not tracks:
        return '<p class="no-data">Aucune donnée SoundCloud disponible.</p>'
    rows = "".join(
        f"<tr><td>{t[0]}</td><td>{t[1]:,}</td><td>{t[2]:,}</td>"
        f"<td>{t[3]:,}</td><td>{t[4]:,}</td></tr>"
        for t in tracks[:5]
    )
    return _html_table(
        ['Titre', 'Plays', 'Likes', 'Reposts', 'Commentaires'], rows)


def _render_apple(apple):
    if not apple:
        return '<p class="no-data">Aucune donnée Apple Music disponible.</p>'
    # KPI only (plays + shazams) — no per-song table (the chart carries the ranking).
    return _kpi_grid(
        _kpi_card(f'{apple["total_plays"]:,}', "Plays totaux")
        + _kpi_card(f'{apple["total_shazams"]:,}', "Shazams")
    )


def _chart(uri, caption=None):
    """Wrap a base64 chart URI in a figure block; empty string if no chart."""
    if not uri:
        return ""
    cap = f'<div class="kpi-lbl" style="text-align:center">{caption}</div>' if caption else ""
    return f'<div class="chart"><img src="{uri}"/>{cap}</div>'


def _render_completeness(data):
    """Top-of-report data-completeness recap: which sources are present vs missing."""
    checks = [
        ("Spotify S4A",            bool(data['streams']['s4a'])),
        ("YouTube",                bool(data.get('youtube_data'))),
        ("Instagram",              bool(data.get('instagram_data'))),
        ("SoundCloud",             bool(data.get('sc_tracks'))),
        ("Apple Music",            bool(data.get('apple_data'))),
        ("Meta Ads",               bool(data.get('meta_data'))),
        ("Hypeddit",               bool(data.get('hypeddit_data'))),
        ("Revenu iMusician",       bool((data.get('roi') or {}).get('revenue_eur'))),
        ("Prédictions ML",         bool(data.get('latest_release'))),
        ("Data Wrapped (saisie)",  bool(data.get('has_wrapped'))),
    ]
    rows = "".join(
        f"<tr><td>{name}</td><td>"
        + ('<span class="badge green">présent</span>' if ok
           else '<span class="badge gray">à renseigner / vide</span>')
        + "</td></tr>"
        for name, ok in checks
    )
    return (f'<table class="compact"><thead><tr><th>Source</th><th>Statut</th></tr>'
            f'</thead><tbody>{rows}</tbody></table>')


def _render_hypeddit(hy):
    if not hy:
        return '<p class="no-data">Aucune donnée Hypeddit disponible.</p>'
    return _kpi_grid(
        _kpi_card(f'{hy["total_visits"]:,}', "Visites (période)")
        + _kpi_card(f'{hy["total_clicks"]:,}', "Clics (période)")
        + _kpi_card(f'{hy["total_budget"]:,.0f} €', "Budget (période)")
    )


def _render_revenue_forecast(rfc):
    if not rfc:
        return '<p class="no-data">Aucune donnée de revenus pour la projection.</p>'
    return _kpi_grid(
        _kpi_card(f'{rfc["total"]:,.0f} €', "Revenu cumulé")
        + _kpi_card(f'{len(rfc["months"])}', "Mois enregistrés")
    )


def _render_score20(rows):
    if not rows:
        return '<p class="no-data">Score /20 indisponible (lancez `ml_scoring_daily`).</p>'
    body = "".join(
        f"<tr><td>{_trunc(s, 42)}</td><td><b>{sc:.1f}</b></td><td>{dw * 100:.0f}%</td>"
        f"<td>{rr * 100:.0f}%</td><td>{ra * 100:.0f}%</td></tr>"
        for s, sc, dw, rr, ra in rows
    )
    note = ("<p class='subtitle'>Score /20 = classement relatif du catalogue "
            "(meilleur = 20, pire = 0) ; pour la proba absolue, lire DW/RR/Radio %.</p>")
    return note + _html_table(['Titre', 'Score /20', 'DW %', 'RR %', 'Radio %'], body)


def _render_overview(data):
    """Home-page KPIs: real per-platform totals + IG followers."""
    s = data['streams']
    ig = data.get('instagram') or {}
    return _kpi_grid(
        _kpi_card(f"{s['total']:,}", "Total streams (toutes plateformes)")
        + _kpi_card(f"{s['s4a']:,}", "Streams Spotify S4A")
        + _kpi_card(f"{s['youtube']:,}", "Vues YouTube")
        + _kpi_card(f"{s['soundcloud']:,}", "Plays SoundCloud")
        + _kpi_card(f"{s['apple']:,}", "Plays Apple Music")
        + _kpi_card(f"{ig.get('followers', 0):,}" if ig else "—", "Followers Instagram")
    )


def _render_credentials(creds):
    if not creds:
        return '<p class="no-data">Statut credentials indisponible.</p>'
    rows = "".join(
        f"<tr><td>{label}</td><td>"
        + ('<span class="badge green">configuré</span>' if ok
           else '<span class="badge gray">non configuré</span>')
        + "</td></tr>"
        for label, ok in creds
    )
    return _html_table(['Plateforme', 'Credentials'], rows)


def _trunc(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _render_mapping(rows):
    if not rows:
        return '<p class="no-data">Aucun mapping campagne ↔ titre saisi.</p>'
    body = "".join(
        f"<tr><td style='width:58%'>{_trunc(c, 46)}</td>"
        f"<td style='width:42%'>{_trunc(t, 34)}</td></tr>"
        for c, t in rows[:15]
    )
    return _html_table(['Campagne Meta', 'Titre'], body)


def render_html(data, artist_name, sections=None):
    """
    Génère la chaîne HTML du rapport.
    sections : dict {key: bool} — si None, toutes les sections sont incluses.
    """
    if sections is None:
        sections = {k: True for k in ALL_SECTIONS}

    gen_dt = data['generated_at'].strftime("%d/%m/%Y à %H:%M")
    period = f"{data['from_date'].strftime('%d/%m/%Y')} → {data['to_date'].strftime('%d/%m/%Y')}"
    charts = data.get('charts', {})

    body_parts = []

    def _sec(html):
        body_parts.append(html)

    # ── État des données : complétude + fraîcheur côte à côte (1ʳᵉ page) ──
    _fresh = (f"<div class='status-col'><h3>📡 Fraîcheur des sources</h3>"
              f"{_render_freshness(data['freshness'])}</div>"
              if sections.get('freshness') else "")
    _sec("<div class='section'><h2>📋 État des données</h2>\n<div class='status-row'>"
         f"<div class='status-col'><h3>📋 Complétude</h3>{_render_completeness(data)}</div>"
         f"{_fresh}</div></div>")

    # ── 🏠 Accueil — vue d'ensemble (vrais totaux par plateforme) ──
    if sections.get('overview'):
        _sec("<div class='section'><h2>🏠 Vue d'ensemble</h2>\n"
             f"{_render_overview(data)}{_chart(charts.get('platform'))}</div>")

    # ── 📁 Données — credentials & mapping ──
    if sections.get('data_setup'):
        _sec("<div class='section'><h2>📁 Données — connexions & mapping</h2>\n"
             f"<h3>Connexions par plateforme</h3>{_render_credentials(data.get('creds_status'))}"
             f"<h3>Mapping campagne ↔ titre</h3>{_render_mapping(data.get('mapping_rows'))}</div>")

    # ── 🎵 Spotify S4A — évolution (TOUT le catalogue, quelle que soit la sélection) ──
    if sections.get('streams'):
        _nc = data.get('n_catalog') or 0
        _sec(f"<div class='section'><h2>🎵 Spotify S4A — évolution</h2>\n"
             f"<p class='subtitle'>Tout le catalogue — {_nc} titres "
             f"(indépendant des chansons sélectionnées).</p>"
             f"{_chart(charts.get('streams'))}{_chart(charts.get('s4a_cumulative'))}"
             f"{_chart(charts.get('s4a_audience'))}</div>")

    # ── 🎵 Spotify S4A — chansons (top OU timeline mono-chanson) ──
    if sections.get('s4a_songs'):
        if data.get('single_song') and charts.get('song_tl'):
            inner = _chart(charts['song_tl'])
        else:
            inner = (_chart(charts.get('s4a_top'))
                     + _render_s4a_top_songs(data.get('s4a_top_songs', [])))
        _sec(f"<div class='section'><h2>🎵 Spotify S4A — chansons</h2>\n{inner}</div>")

    if sections.get('meta_x_spotify'):
        mxs = (_chart(charts.get('mxs')) if charts.get('mxs')
               else '<p class="no-data">Pas assez de données campagne/streams.</p>')
        _sec(f"<div class='section'><h2>🔗 Meta × Spotify</h2>\n{mxs}</div>")

    if sections.get('apple'):
        _single = data.get('single_song')
        ad = data.get('apple_data')
        if _single:
            _h = f"🍎 Apple Music — {_single}"
        elif data.get('report_n'):
            _h = "🍎 Apple Music — titres sélectionnés"
        else:
            _h = "🍎 Apple Music (cumul carrière)"
        if _single and (not ad or not ad.get('top_songs')):
            inner = '<p class="no-data">Pas de données pour cette chanson sur Apple Music.</p>'
        elif _single:
            inner = _render_apple(ad) + _chart(charts.get('apple_daily'))
        else:
            inner = (_chart(charts.get('apple')) + _render_apple(ad)
                     + _chart(charts.get('apple_daily')))
        _sec(f"<div class='section'><h2>{_h}</h2>\n{inner}</div>")

    if sections.get('youtube'):
        yd = data.get('youtube_data')
        if data.get('single_song') and yd and not yd.get('videos'):
            vid = '<p class="no-data">Pas de vidéo YouTube identifiée pour cette chanson.</p>'
        else:
            vid = _chart(charts.get('youtube'))
        _sec("<div class='section'><h2>🎬 YouTube</h2>\n"
             f"{_chart(charts.get('yt_growth'))}{vid}\n{_render_youtube(yd)}</div>")

    if sections.get('soundcloud_detail'):
        _single = data.get('single_song')
        sct = data.get('sc_tracks', [])
        _h = (f"☁️ SoundCloud — {_single}" if _single else "☁️ SoundCloud (cumul carrière)")
        _ts = _chart(charts.get('sc_multi'))
        if _single and not sct:
            inner = '<p class="no-data">Pas de données pour cette chanson sur SoundCloud.</p>'
        elif _single:
            inner = _ts + _render_soundcloud_tracks(sct)
        else:
            inner = _chart(charts.get('soundcloud')) + _ts + _render_soundcloud_tracks(sct)
        _sec(f"<div class='section'><h2>{_h}</h2>\n{inner}</div>")

    if sections.get('instagram'):
        _sec("<div class='section'><h2>📸 Instagram</h2>\n"
             f"{_chart(charts.get('instagram'))}{_chart(charts.get('ig_engagement'))}\n"
             f"{_render_instagram(data.get('instagram_data'))}</div>")

    if sections.get('hypeddit'):
        _sec("<div class='section'><h2>📣 Hypeddit</h2>\n"
             f"{_render_hypeddit(data.get('hypeddit_data'))}\n"
             f"{_chart(charts.get('hypeddit'))}{_chart(charts.get('hypeddit_camps'))}</div>")

    # ── 🔮 Prédiction algos (focus algo + chansons ML) — déplacé ici ──
    if sections.get('songs'):
        _focus = data.get('single_song') or data.get('latest_release')
        head = f"<div class='song-title'>🚀 {_focus}</div>" if _focus else ""
        score = (f"<h3>🏆 Score /20 — tracks du rapport</h3>"
                 f"{_render_score20(data.get('score20'))}")
        _j28_note = (
            "<p class='subtitle'>Courbe = streams cumulés du titre sur ses 28 premiers jours. "
            "À titre de repère, lorsqu'une playlist algorithmique se déclenche elle génère "
            "elle-même un volume d'algo-streams (sur 28j) qui démarre autour de "
            "<b>~130 (Release Radar)</b>, <b>~137 (Discover Weekly)</b>, <b>~639 (Radio)</b> "
            "et se stabilise vers <b>~417 / ~1 333 / ~8 423</b> une fois installée. Ce sont des "
            "volumes <b>produits par les playlists</b> (signal de détection), <b>pas</b> un "
            "objectif de streams à atteindre soi-même pour les déclencher.</p>"
            if charts.get('j28') else "")
        inner = (head + _chart(charts.get('ml')) + _chart(charts.get('j28')) + _j28_note
                 + _chart(charts.get('playlist_adds')) + _chart(charts.get('pi_gate'))
                 + score
                 + (_render_songs_focus(data['songs_data']) if data.get('songs_data') else ""))
        inner = inner or '<p class="no-data">Pas de prédiction ML.</p>'
        _sec(f"<div class='section'><h2>🔮 Prédiction algorithmique (J+28)</h2>\n{inner}</div>")

    # ── 🔬 Explainabilité ML — SHAP waterfalls (DW/RR/Radio) + curseurs par track ──
    if sections.get('ml_explain'):
        from src.dashboard.utils import pdf_ml
        blocks = []
        for track, fj in data.get('ml_explain', []):
            wf = "".join(
                f"<div class='song-title'>{lbl}</div>{_chart(uri)}{narr}"
                for (lbl, uri, narr) in pdf_ml.shap_waterfalls(fj)
            )
            cur = pdf_ml.decision_cursors_html(fj)
            body = ((wf or "<p class='no-data'>SHAP indisponible pour cette chanson.</p>")
                    + "<h3>🎚️ Curseurs de décision (DW · RR · Radio)</h3>"
                    + (cur or "<p class='no-data'>Curseurs indisponibles.</p>"))
            # Plain wrapper (no .section → no page-break-inside:avoid): each track block
            # spans multiple pages, so "avoid" would only orphan the heading on a blank page.
            blocks.append(f"<div class='ml-track'><h3>🔬 {track}</h3>{body}</div>")
        if data.get('ml_explain_truncated'):
            blocks.append("<p class='subtitle'>(Limité aux 5 premières chansons du rapport.)</p>")
        inner = "".join(blocks) or '<p class="no-data">Aucune prédiction ML disponible.</p>'
        # No outer .section wrapper here (its page-break-inside:avoid would push the whole
        # multi-page block down, leaving the heading alone on a blank page).
        _sec(f"<h2>🔬 Explainabilité ML (SHAP &amp; curseurs)</h2>{inner}")

    if sections.get('meta'):
        _sec("<div class='section'><h2>📱 Meta Ads (cumul carrière)</h2>\n"
             f"{_chart(charts.get('meta'))}{_chart(charts.get('meta_funnel'))}"
             f"{_chart(charts.get('meta_daily'))}\n{_render_meta(data.get('meta_data'))}</div>")

    if sections.get('meta_breakdowns'):
        bd = (f"{_chart(charts.get('bd_country'))}{_chart(charts.get('bd_placement'))}"
              f"{_chart(charts.get('bd_age'))}")
        if not bd.strip():
            bd = '<p class="no-data">Aucune répartition Meta disponible.</p>'
        _sec(f"<div class='section'><h2>🌍 Meta — Répartitions (pays · placement · âge)</h2>\n{bd}</div>")

    if sections.get('roi'):
        _sec("<div class='section'><h2>💹 ROI Breakeven</h2>\n"
             f"{_render_roi(data['roi'], data['from_date'], data['to_date'])}\n"
             f"{_chart(charts.get('roi'))}</div>")

    if sections.get('revenue_forecast'):
        _sec("<div class='section'><h2>📈 Prévisions revenus</h2>\n"
             f"{_render_revenue_forecast(data.get('revenue_fc'))}\n"
             f"{_chart(charts.get('revenue_fc'))}</div>")

    body_html = "\n\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Rapport — {artist_name}</title>
<style>{_CSS}</style></head>
<body>
<div class="cover">
  <div class="cov-logo">{_logo_svg()}</div>
  <div class="eyebrow">Rapport artiste</div>
  <h1>{artist_name}</h1>
  <div class="meta">Période : {period}<br>Généré le {gen_dt}</div>
</div>

<div class="content">
  {body_html}

  <div class="footer">
    Généré automatiquement par streaMLytics &nbsp;|&nbsp;
    Confidentiel — ne pas diffuser sans autorisation &nbsp;|&nbsp; {gen_dt}
  </div>
</div>
</body>
</html>"""


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def generate_pdf(db, artist_id, artist_name=None, months=12,
                 from_date=None, to_date=None,
                 sections=None, songs=None, s4a_songs_filter=None):
    """
    Collecte les données et retourne les bytes du PDF.

    Paramètres :
        months    — période en mois (ignoré si from_date/to_date fournis)
        from_date / to_date — dates de début/fin (prioritaires sur months)
        sections  — dict {key: bool} des sections à inclure (None = toutes)
        songs     — liste de noms de chansons pour la section focus
    """
    from weasyprint import HTML

    now = datetime.now()
    if from_date is None:
        from_date = (now - relativedelta(months=months)).replace(day=1).date()
    if to_date is None:
        to_date = now.date()
    if artist_name is None:
        artist_name = _get_artist_name(db, artist_id)

    data = collect_report_data(db, artist_id, from_date, to_date, songs=songs,
                               s4a_songs_filter=s4a_songs_filter)
    html_str = _EMOJI_RE.sub("", render_html(data, artist_name, sections=sections))
    return HTML(string=html_str).write_pdf()
