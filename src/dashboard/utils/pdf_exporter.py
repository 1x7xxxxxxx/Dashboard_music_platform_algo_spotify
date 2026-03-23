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
    'freshness': '📡 Fraîcheur des sources',
    'streams':   '🎧 Streams totaux',
    'kpi':       '📊 KPI (Spotify, Instagram, SoundCloud)',
    'roi':       '💹 ROI Breakheaven',
    'songs':     '🎵 Focus chansons',
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
                       WHERE song = %s AND artist_id = %s AND date BETWEEN %s AND %s""",
                    (song, artist_id, from_date, to_date)
                )
            else:
                row = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0)
                       FROM s4a_song_timeline
                       WHERE song = %s AND date BETWEEN %s AND %s""",
                    (song, from_date, to_date)
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
                       WHERE song = %s AND artist_id = %s
                         AND date >= CURRENT_DATE - INTERVAL '7 days'""",
                    (song, artist_id)
                )
            else:
                row = db.fetch_query(
                    """SELECT COALESCE(SUM(streams), 0)
                       FROM s4a_song_timeline
                       WHERE song = %s AND date >= CURRENT_DATE - INTERVAL '7 days'""",
                    (song,)
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


def collect_report_data(db, artist_id, from_date, to_date, songs=None):
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

    songs_data = _collect_songs_focus(db, artist_id, songs, from_date, to_date) if songs else []

    return {
        'generated_at': now,
        'period_months': months,
        'from_date': from_date,
        'to_date': to_date,
        'freshness': freshness,
        'streams': {'s4a': s4a, 'youtube': yt, 'soundcloud': sc, 'apple': apple,
                    'total': s4a + yt + sc + apple},
        'spotify_popularity': pop,
        'instagram': ig,
        'soundcloud_likes': likes,
        'roi': roi,
        'songs_data': songs_data,
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
    if sections.get('songs') and data.get('songs_data'):
        body_parts.append(
            f"<h2>🎵 Focus chansons</h2>\n{_render_songs_focus(data['songs_data'])}"
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
                 sections=None, songs=None):
    """
    Collecte les données et retourne les bytes du PDF.

    Paramètres :
        months    — période en mois (ignoré si from_date/to_date fournis)
        from_date / to_date — dates de début/fin (prioritaires sur months)
        sections  — dict {key: bool} des sections à inclure (None = toutes)
        songs     — liste de noms de chansons pour la section focus
    """
    from weasyprint import HTML  # import tardif

    now = datetime.now()
    if from_date is None:
        from_date = (now - relativedelta(months=months)).replace(day=1).date()
    if to_date is None:
        to_date = now.date()
    if artist_name is None:
        artist_name = _get_artist_name(db, artist_id)

    data = collect_report_data(db, artist_id, from_date, to_date, songs=songs)
    html_str = render_html(data, artist_name, sections=sections)
    return HTML(string=html_str).write_pdf()
