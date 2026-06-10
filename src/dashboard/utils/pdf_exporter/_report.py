"""PDF export — report layer (move-only split of pdf_exporter)."""
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, get_total_streams_s4a, get_total_views_youtube,
    get_total_plays_soundcloud, get_total_plays_apple,
    get_spotify_popularity, get_instagram_followers, get_soundcloud_likes,
    get_roi_data,
    ARTIST_NAME_FILTER,
)
from ._config import ALL_SECTIONS, _CSS, _EMOJI_RE, _logo_svg
from ._collectors import (
    _collect_apple, _collect_apple_timeline, _collect_credentials_status, _collect_hypeddit, _collect_hypeddit_campaigns, _collect_ig_monthly, _collect_instagram, _collect_j28, _collect_mapping, _collect_meta, _collect_meta_breakdowns, _collect_meta_daily, _collect_meta_funnel, _collect_meta_x_spotify, _collect_ml_explain, _collect_pi_gate, _collect_playlist_adds_windows, _collect_revenue_forecast, _collect_s4a_audience, _collect_s4a_daily, _collect_s4a_top_songs, _collect_sc_series, _collect_score20, _collect_song_timeline, _collect_songs_focus, _collect_soundcloud_tracks, _collect_youtube, _collect_youtube_history, _get_artist_name, _has_wrapped, _latest_release,
)
from ._renderers import (
    _chart, _render_apple, _render_completeness, _render_credentials, _render_freshness, _render_hypeddit, _render_instagram, _render_mapping, _render_meta, _render_overview, _render_revenue_forecast, _render_roi, _render_s4a_top_songs, _render_score20, _render_songs_focus, _render_soundcloud_tracks, _render_youtube,
)



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
