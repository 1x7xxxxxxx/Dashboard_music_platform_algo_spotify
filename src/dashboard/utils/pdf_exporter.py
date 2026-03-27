"""Génération de rapports PDF artiste via WeasyPrint."""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
    get_total_streams_s4a, get_total_views_youtube,
    get_total_plays_soundcloud, get_total_plays_apple,
    get_spotify_popularity, get_instagram_followers, get_soundcloud_likes,
    get_roi_data,
    ARTIST_NAME_FILTER,
)

# Sections disponibles dans le rapport (ordre d'affichage)
ALL_SECTIONS = {
    'freshness':          '📡 Fraîcheur des sources',
    'streams':            '🎧 Streams totaux',
    'kpi':                '📊 KPI (Spotify, Instagram, SoundCloud)',
    'roi':                '💹 ROI Breakheaven',
    's4a_songs':          '🎵 Spotify S4A — Top chansons',
    'youtube':            '🎬 YouTube',
    'instagram':          '📸 Instagram',
    'meta':               '📱 Meta Ads',
    'soundcloud_detail':  '☁️ SoundCloud — Tracks',
    'apple':              '🍎 Apple Music',
    'songs':              '🔬 Focus chansons (ML)',
}

# ─── CSS ─────────────────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
       font-size: 11pt; color: #1a1a2e; background: #fff; }
.page { padding: 28px 36px; max-width: 900px; margin: auto; }
h1  { font-size: 20pt; color: #1DB954; margin-bottom: 4px; }
h2  { font-size: 13pt; color: #1a1a2e; border-left: 4px solid #1DB954;
      padding-left: 8px; margin: 22px 0 10px 0; }
h3  { font-size: 10.5pt; color: #444; margin: 14px 0 6px 0; }
.subtitle { color: #666; font-size: 9pt; margin-bottom: 24px; }
table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
th  { background: #1DB954; color: #fff; font-size: 9.5pt;
      padding: 6px 10px; text-align: left; }
td  { padding: 5px 10px; font-size: 10pt; border-bottom: 1px solid #eee; }
tr:nth-child(even) td { background: #f8f8f8; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 8.5pt; font-weight: 600; color: #fff; }
.green  { background: #1DB954; }
.orange { background: #FFA500; }
.red    { background: #FF4444; }
.gray   { background: #888; }
.kpi-grid { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; }
.kpi-card { flex: 1; min-width: 130px; border: 1px solid #e0e0e0;
            border-radius: 8px; padding: 10px 14px; text-align: center; }
.kpi-val  { font-size: 17pt; font-weight: 800; color: #1DB954; }
.kpi-lbl  { font-size: 8pt; color: #666; margin-top: 2px; }
.roi-card { background: #f0faf3; border: 1px solid #1DB954; border-radius: 8px;
            padding: 14px 18px; margin-bottom: 12px; }
.roi-row  { display: flex; gap: 32px; }
.roi-item { flex: 1; }
.song-block { border: 1px solid #e0e0e0; border-radius: 8px;
              padding: 12px 16px; margin-bottom: 14px; }
.song-title { font-weight: 700; font-size: 11pt; color: #1DB954;
              margin-bottom: 8px; }
.prob-bar-wrap { background: #eee; border-radius: 4px; height: 10px;
                 width: 100%; margin: 2px 0 6px 0; }
.prob-bar { background: #1DB954; border-radius: 4px; height: 10px; }
.no-data  { color: #aaa; font-style: italic; font-size: 9pt; }
.footer   { margin-top: 36px; font-size: 7.5pt; color: #aaa; text-align: center;
            border-top: 1px solid #eee; padding-top: 10px; }
"""

# ─── Helpers DB ───────────────────────────────────────────────────────────────

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


def _collect_youtube(db, artist_id):
    """Stats chaîne + top 10 vidéos par vues."""
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
        return {
            'subscriber_count': subs,
            'total_views':      views,
            'videos': [
                (r[0], str(r[1])[:10] if r[1] else '—',
                 int(r[2] or 0), int(r[3] or 0), int(r[4] or 0))
                for r in vids
            ] if vids else [],
        }
    except Exception:
        return None


def _collect_instagram(db, artist_id):
    """Derniers stats + historique 30 jours (agrégé par jour)."""
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
               WHERE artist_id = %s
                 AND collected_at >= CURRENT_DATE - INTERVAL '30 days'
               GROUP BY collected_at::date ORDER BY collected_at::date""",
            (artist_id,),
        )
        return {
            'username':    username or '—',
            'followers':   int(followers or 0),
            'media_count': int(media_count or 0),
            'history':     [(str(r[0]), int(r[1] or 0)) for r in history] if history else [],
        }
    except Exception:
        return None


def _collect_meta(db, artist_id):
    """Résumé des campagnes Meta Ads."""
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            """SELECT campaign_name, spend, results, impressions, reach, link_clicks
               FROM meta_insights_performance
               WHERE artist_id = %s ORDER BY spend DESC""",
            (artist_id,),
        )
        if not rows:
            return None
        campaigns = [
            (r[0], float(r[1] or 0), int(r[2] or 0),
             int(r[3] or 0), int(r[4] or 0), int(r[5] or 0))
            for r in rows
        ]
        return {
            'campaigns':     campaigns,
            'total_spend':   sum(c[1] for c in campaigns),
            'total_results': sum(c[2] for c in campaigns),
        }
    except Exception:
        return None


def _collect_soundcloud_tracks(db, artist_id):
    """Dernier snapshot de tous les tracks SoundCloud (trié par plays)."""
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
        if not rows:
            return []
        return sorted(
            [(r[0], int(r[1] or 0), int(r[2] or 0), int(r[3] or 0), int(r[4] or 0))
             for r in rows],
            key=lambda x: -x[1],
        )
    except Exception:
        return []


def _collect_apple(db, artist_id):
    """Apple Music : totaux + top 10 chansons."""
    if artist_id is None:
        return None
    try:
        totals = db.fetch_query(
            """SELECT COALESCE(SUM(plays), 0), COALESCE(SUM(shazam_count), 0)
               FROM apple_songs_performance WHERE artist_id = %s""",
            (artist_id,),
        )
        top = db.fetch_query(
            """SELECT song_name, plays FROM apple_songs_performance
               WHERE artist_id = %s ORDER BY plays DESC LIMIT 10""",
            (artist_id,),
        )
        return {
            'total_plays':   int(totals[0][0] or 0) if totals else 0,
            'total_shazams': int(totals[0][1] or 0) if totals else 0,
            'top_songs':     [(r[0], int(r[1] or 0)) for r in top] if top else [],
        }
    except Exception:
        return None


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
    roi   = get_roi_data(db, artist_id, from_date, to_date)

    songs_data       = _collect_songs_focus(db, artist_id, songs, from_date, to_date) if songs else []
    s4a_top_songs    = _collect_s4a_top_songs(db, artist_id, from_date, to_date, songs_filter=s4a_songs_filter)
    youtube_data     = _collect_youtube(db, artist_id)
    instagram_data   = _collect_instagram(db, artist_id)
    meta_data        = _collect_meta(db, artist_id)
    sc_tracks        = _collect_soundcloud_tracks(db, artist_id)
    apple_data       = _collect_apple(db, artist_id)

    return {
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
    }


# ─── Rendu HTML ──────────────────────────────────────────────────────────────

def _badge(emoji, label):
    css = {'🟢': 'green', '🟠': 'orange', '🔴': 'red'}.get(emoji, 'gray')
    return f'<span class="badge {css}">{emoji} {label}</span>'


def _render_freshness(freshness):
    rows = []
    for label, info in freshness.items():
        emoji, _, age_label = freshness_status(info['last_dt'])
        date_str = info['last_dt'].strftime("%d/%m/%Y %H:%M") if info['last_dt'] else "—"
        rows.append(
            f"<tr><td>{info['icon']} {label}</td>"
            f"<td>{_badge(emoji, age_label)}</td>"
            f"<td>{date_str}</td></tr>"
        )
    return f"""<table>
      <thead><tr><th>Source</th><th>Statut</th><th>Dernière MAJ</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>"""


def _render_streams(streams):
    items = [
        ("🎵 Spotify S4A", streams['s4a']),
        ("🎬 YouTube",      streams['youtube']),
        ("☁️ SoundCloud",   streams['soundcloud']),
        ("🍎 Apple Music",  streams['apple']),
    ]
    total_card = (
        f'<div class="kpi-card" style="border-color:#1DB954; background:#f0faf3;">'
        f'<div class="kpi-val" style="font-size:22pt;">{streams["total"]:,}</div>'
        f'<div class="kpi-lbl">🎧 Total toutes plateformes</div></div>'
    )
    cards = "".join(
        f'<div class="kpi-card"><div class="kpi-val">{v:,}</div>'
        f'<div class="kpi-lbl">{lbl}</div></div>'
        for lbl, v in items
    )
    return f'<div class="kpi-grid">{total_card}{cards}</div>'


def _render_kpi(pop, ig, likes, sc_plays):
    rows = []
    if pop:
        rows.append(
            f"<tr><td>🎵 Spotify Popularity</td><td><b>{pop['score']} / 100</b></td>"
            f"<td>{pop['track']}</td></tr>"
        )
    if ig:
        rows.append(
            f"<tr><td>📸 Instagram Followers</td><td><b>{ig['followers']:,}</b></td>"
            f"<td>{ig['date']}</td></tr>"
        )
    rows.append(
        f"<tr><td>☁️ SoundCloud Plays</td><td><b>{sc_plays:,}</b></td>"
        f"<td>❤️ {likes:,} likes</td></tr>"
    )
    return f"""<table>
      <thead><tr><th>Métrique</th><th>Valeur</th><th>Détail</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>"""


def _render_roi(roi, from_date, to_date):
    roi_val = f"{roi['roi_pct']:.1f} %" if roi['roi_pct'] is not None else "—"
    status  = "✅ Rentable" if roi['profitable'] else "⚠️ Déficitaire"
    period  = f"{from_date.strftime('%d/%m/%Y')} → {to_date.strftime('%d/%m/%Y')}"
    return f"""
    <div class="roi-card">
      <p style="font-size:8.5pt;color:#555;margin-bottom:10px;">Période : {period}</p>
      <div class="roi-row">
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;">{roi['revenue_eur']:,.2f} €</div>
          <div class="kpi-lbl">💰 Revenus iMusician</div>
        </div>
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;color:#FF4444;">{roi['meta_spend']:,.2f} €</div>
          <div class="kpi-lbl">📱 Dépenses Meta Ads</div>
        </div>
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;">{roi_val}</div>
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
        for s in songs
    )
    return (
        f'<table><thead><tr><th>Chanson</th><th>Streams (période)</th>'
        f'<th>Streams 7 derniers jours</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _render_youtube(yt):
    if not yt:
        return '<p class="no-data">Aucune donnée YouTube disponible.</p>'
    header = (
        f'<div class="kpi-grid">'
        f'<div class="kpi-card"><div class="kpi-val">{yt["subscriber_count"]:,}</div>'
        f'<div class="kpi-lbl">Abonnés</div></div>'
        f'<div class="kpi-card"><div class="kpi-val">{yt["total_views"]:,}</div>'
        f'<div class="kpi-lbl">Vues totales (chaîne)</div></div>'
        f'</div>'
    )
    if not yt['videos']:
        return header + '<p class="no-data">Aucune vidéo trouvée.</p>'
    rows = "".join(
        f"<tr><td>{v[0]}</td><td>{v[1]}</td>"
        f"<td>{v[2]:,}</td><td>{v[3]:,}</td><td>{v[4]:,}</td></tr>"
        for v in yt['videos']
    )
    table = (
        f'<table><thead><tr><th>Titre</th><th>Publiée</th>'
        f'<th>Vues</th><th>Likes</th><th>Commentaires</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )
    return header + table


def _render_instagram(ig):
    if not ig:
        return '<p class="no-data">Aucune donnée Instagram disponible.</p>'
    summary = (
        f'<div class="kpi-grid">'
        f'<div class="kpi-card"><div class="kpi-val">{ig["followers"]:,}</div>'
        f'<div class="kpi-lbl">@{ig["username"]} — Abonnés</div></div>'
        f'<div class="kpi-card"><div class="kpi-val">{ig["media_count"]:,}</div>'
        f'<div class="kpi-lbl">Publications</div></div>'
        f'</div>'
    )
    if not ig['history']:
        return summary
    rows = "".join(
        f"<tr><td>{h[0]}</td><td>{h[1]:,}</td></tr>"
        for h in ig['history'][-10:]
    )
    table = (
        f'<h3>Évolution abonnés — 10 dernières entrées (30 j)</h3>'
        f'<table><thead><tr><th>Date</th><th>Abonnés</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )
    return summary + table


def _render_meta(meta):
    if not meta or not meta['campaigns']:
        return '<p class="no-data">Aucune donnée Meta Ads disponible.</p>'
    summary = (
        f'<div class="kpi-grid">'
        f'<div class="kpi-card"><div class="kpi-val" style="color:#FF4444;">'
        f'{meta["total_spend"]:,.2f} €</div>'
        f'<div class="kpi-lbl">Dépenses totales</div></div>'
        f'<div class="kpi-card"><div class="kpi-val">{meta["total_results"]:,}</div>'
        f'<div class="kpi-lbl">Résultats totaux</div></div>'
        f'</div>'
    )
    rows = "".join(
        f"<tr><td>{c[0]}</td><td>{c[1]:,.2f} €</td><td>{c[2]:,}</td>"
        f"<td>{c[3]:,}</td><td>{c[4]:,}</td><td>{c[5]:,}</td></tr>"
        for c in meta['campaigns']
    )
    table = (
        f'<table><thead><tr><th>Campagne</th><th>Dépenses</th><th>Résultats</th>'
        f'<th>Impressions</th><th>Reach</th><th>Clics</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )
    return summary + table


def _render_soundcloud_tracks(tracks):
    if not tracks:
        return '<p class="no-data">Aucune donnée SoundCloud disponible.</p>'
    rows = "".join(
        f"<tr><td>{t[0]}</td><td>{t[1]:,}</td><td>{t[2]:,}</td>"
        f"<td>{t[3]:,}</td><td>{t[4]:,}</td></tr>"
        for t in tracks
    )
    return (
        f'<table><thead><tr><th>Titre</th><th>Plays</th><th>Likes</th>'
        f'<th>Reposts</th><th>Commentaires</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _render_apple(apple):
    if not apple:
        return '<p class="no-data">Aucune donnée Apple Music disponible.</p>'
    summary = (
        f'<div class="kpi-grid">'
        f'<div class="kpi-card"><div class="kpi-val">{apple["total_plays"]:,}</div>'
        f'<div class="kpi-lbl">Plays totaux</div></div>'
        f'<div class="kpi-card"><div class="kpi-val">{apple["total_shazams"]:,}</div>'
        f'<div class="kpi-lbl">Shazams</div></div>'
        f'</div>'
    )
    if not apple['top_songs']:
        return summary
    rows = "".join(
        f"<tr><td>{s[0]}</td><td>{s[1]:,}</td></tr>"
        for s in apple['top_songs']
    )
    table = (
        f'<table><thead><tr><th>Chanson</th><th>Plays</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )
    return summary + table


def render_html(data, artist_name, sections=None):
    """
    Génère la chaîne HTML du rapport.
    sections : dict {key: bool} — si None, toutes les sections sont incluses.
    """
    if sections is None:
        sections = {k: True for k in ALL_SECTIONS}

    gen_dt = data['generated_at'].strftime("%d/%m/%Y à %H:%M")
    period = f"{data['from_date'].strftime('%d/%m/%Y')} → {data['to_date'].strftime('%d/%m/%Y')}"

    body_parts = []

    if sections.get('freshness'):
        body_parts.append(
            f"<h2>📡 Fraîcheur des données</h2>\n{_render_freshness(data['freshness'])}"
        )
    if sections.get('streams'):
        body_parts.append(
            f"<h2>🎧 Streams totaux</h2>\n{_render_streams(data['streams'])}"
        )
    if sections.get('kpi'):
        body_parts.append(
            f"<h2>📊 KPI</h2>\n"
            f"{_render_kpi(data['spotify_popularity'], data['instagram'], data['soundcloud_likes'], data['streams']['soundcloud'])}"
        )
    if sections.get('roi'):
        body_parts.append(
            f"<h2>💹 ROI Breakheaven</h2>\n"
            f"{_render_roi(data['roi'], data['from_date'], data['to_date'])}"
        )
    if sections.get('s4a_songs'):
        body_parts.append(
            f"<h2>🎵 Spotify S4A — Top chansons</h2>\n"
            f"{_render_s4a_top_songs(data.get('s4a_top_songs', []))}"
        )
    if sections.get('youtube'):
        body_parts.append(
            f"<h2>🎬 YouTube</h2>\n"
            f"{_render_youtube(data.get('youtube_data'))}"
        )
    if sections.get('instagram'):
        body_parts.append(
            f"<h2>📸 Instagram</h2>\n"
            f"{_render_instagram(data.get('instagram_data'))}"
        )
    if sections.get('meta'):
        body_parts.append(
            f"<h2>📱 Meta Ads</h2>\n"
            f"{_render_meta(data.get('meta_data'))}"
        )
    if sections.get('soundcloud_detail'):
        body_parts.append(
            f"<h2>☁️ SoundCloud — Tracks</h2>\n"
            f"{_render_soundcloud_tracks(data.get('sc_tracks', []))}"
        )
    if sections.get('apple'):
        body_parts.append(
            f"<h2>🍎 Apple Music</h2>\n"
            f"{_render_apple(data.get('apple_data'))}"
        )
    if sections.get('songs') and data.get('songs_data'):
        body_parts.append(
            f"<h2>🔬 Focus chansons (ML)</h2>\n{_render_songs_focus(data['songs_data'])}"
        )

    body_html = "\n\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Rapport — {artist_name}</title>
<style>{_CSS}</style></head>
<body>
<div class="page">
  <h1>🎵 Music Platform Dashboard</h1>
  <div class="subtitle">
    Rapport artiste — <b>{artist_name}</b><br>
    Période : {period} &nbsp;|&nbsp; Généré le {gen_dt}
  </div>

  {body_html}

  <div class="footer">
    Généré automatiquement par Music Platform Dashboard &nbsp;|&nbsp;
    Ne pas diffuser sans autorisation &nbsp;|&nbsp; {gen_dt}
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
    import io
    from xhtml2pdf import pisa  # pure-Python, no system deps

    now = datetime.now()
    if from_date is None:
        from_date = (now - relativedelta(months=months)).replace(day=1).date()
    if to_date is None:
        to_date = now.date()
    if artist_name is None:
        artist_name = _get_artist_name(db, artist_id)

    data = collect_report_data(db, artist_id, from_date, to_date, songs=songs,
                               s4a_songs_filter=s4a_songs_filter)
    html_str = render_html(data, artist_name, sections=sections)
    buf = io.BytesIO()
    result = pisa.CreatePDF(html_str, dest=buf)
    if result.err:
        raise RuntimeError(f"PDF generation failed: {result.err}")
    return buf.getvalue()
