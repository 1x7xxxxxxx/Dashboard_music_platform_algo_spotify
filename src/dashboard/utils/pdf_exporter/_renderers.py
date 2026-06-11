"""PDF export — renderers layer (move-only split of pdf_exporter)."""
import src.dashboard.utils.pdf_exporter as _pkg

from ._config import _t



def _badge(emoji, label):
    css = {'🟢': 'green', '🟠': 'orange', '🔴': 'red'}.get(emoji, 'gray')
    return f'<span class="badge {css}">{emoji} {label}</span>'


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
        emoji, _, age_label = _pkg.freshness_status(info['last_dt'])
        rows.append(
            f"<tr><td>{info['icon']} {label}</td>"
            f"<td>{_badge(emoji, age_label)}</td></tr>"
        )
    _h_source = _t("pdf.col.source", "Source")
    _h_last = _t("pdf.col.last_collect", "Dernière collecte")
    return f"""<table class="compact">
      <thead><tr><th>{_h_source}</th><th>{_h_last}</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>"""


def _render_streams(streams):
    items = [
        ("🎵 Spotify S4A", streams['s4a']),
        ("🎬 YouTube",      streams['youtube']),
        ("☁️ SoundCloud",   streams['soundcloud']),
        ("🍎 Apple Music",  streams['apple']),
    ]
    total_card = _kpi_card(
        f'{streams["total"]:,}', _t("pdf.kpi.total_all_platforms", "🎧 Total toutes plateformes"),
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
    status = (_t("pdf.roi.profitable", "✅ Rentable") if net >= 0
              else _t("pdf.roi.deficit", "⚠️ Déficitaire"))
    since_start = _t("pdf.roi.since_start", "Depuis le début (tout l'historique)")
    lbl_rev = _t("pdf.roi.revenue_total", "💰 Revenus (iMusician + DistroKid + SACEM)")
    lbl_spend = _t("pdf.roi.spend_meta", "📱 Dépenses Meta Ads")
    lbl_net = _t("pdf.roi.net", "Net (revenus − dépenses)")
    return f"""
    <div class="roi-card">
      <p style="font-size:8.5pt;color:#555;margin-bottom:10px;">{since_start}</p>
      <div class="roi-row">
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;">{rev:,.2f} €</div>
          <div class="kpi-lbl">{lbl_rev}</div>
        </div>
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;color:#FF4444;">{spend:,.2f} €</div>
          <div class="kpi-lbl">{lbl_spend}</div>
        </div>
        <div class="roi-item">
          <div class="kpi-val" style="font-size:14pt;color:{net_color};">{net:,.2f} €</div>
          <div class="kpi-lbl">{lbl_net}</div>
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
        return f'<p class="no-data">{_t("pdf.nodata.no_song_selected", "Aucune chanson sélectionnée.")}</p>'
    th_dw = _t("pdf.col.dw_playlist", "DW Playlist")
    th_rr = _t("pdf.col.release_radar", "Release Radar")
    th_radio = _t("pdf.col.radio", "Radio")
    th_fc_dw = _t("pdf.col.forecast_dw_7d", "Forecast DW 7j")
    th_fc_rr = _t("pdf.col.forecast_rr_7d", "Forecast RR 7j")
    word_streams = _t("pdf.word.streams", "streams")
    no_ml = _t("pdf.nodata.no_ml_prediction", "Pas de prédiction ML disponible.")
    lbl_period = _t("pdf.label.streams_period", "Streams (période)")
    lbl_last7 = _t("pdf.label.streams_last7d", "Streams 7 derniers jours")
    parts = []
    for s in songs_data:
        ml = s['ml']
        if ml:
            pred_on = _t("pdf.label.prediction_on", "Prédiction du {date}").format(
                date=ml['prediction_date'])
            ml_html = f"""
            <table style="width:100%;margin-top:8px;">
              <thead><tr>
                <th>{th_dw}</th><th>{th_rr}</th><th>{th_radio}</th>
                <th>{th_fc_dw}</th><th>{th_fc_rr}</th>
              </tr></thead>
              <tbody><tr>
                <td>{_prob_bar(ml['dw_prob'])}</td>
                <td>{_prob_bar(ml['rr_prob'])}</td>
                <td>{_prob_bar(ml['radio_prob'])}</td>
                <td><b>{int(ml['dw_forecast']):,}</b> {word_streams}</td>
                <td><b>{int(ml['rr_forecast']):,}</b> {word_streams}</td>
              </tr></tbody>
            </table>
            <p style="font-size:7.5pt;color:#aaa;margin-top:4px;">
              {pred_on}
            </p>"""
        else:
            ml_html = f'<p class="no-data" style="margin-top:6px;">{no_ml}</p>'

        parts.append(f"""
        <div class="song-block">
          <div class="song-title">🎵 {s['song']}</div>
          <table style="width:auto;margin-bottom:0;">
            <tr>
              <td style="padding:3px 16px 3px 0;border:none;">
                {lbl_period} : <b>{s['total_streams']:,}</b>
              </td>
              <td style="padding:3px 0;border:none;">
                {lbl_last7} : <b>{s['last7d_streams']:,}</b>
              </td>
            </tr>
          </table>
          {ml_html}
        </div>""")
    return "\n".join(parts)


def _render_s4a_top_songs(songs):
    if not songs:
        return f'<p class="no-data">{_t("pdf.nodata.s4a", "Aucune donnée S4A disponible.")}</p>'
    rows = "".join(
        f"<tr><td>{s[0]}</td><td>{s[1]:,}</td><td>{s[2]:,}</td></tr>"
        for s in songs[:5]
    )
    return _html_table(
        [_t("pdf.col.song", "Chanson"),
         _t("pdf.label.streams_period", "Streams (période)"),
         _t("pdf.label.streams_last7d", "Streams 7 derniers jours")], rows)


def _render_youtube(yt):
    if not yt:
        return f'<p class="no-data">{_t("pdf.nodata.youtube", "Aucune donnée YouTube disponible.")}</p>'
    # KPI header only — the growth + top-videos charts carry the detail (no table).
    return _kpi_grid(
        _kpi_card(f'{yt["subscriber_count"]:,}', _t("pdf.kpi.subscribers", "Abonnés"))
        + _kpi_card(f'{yt["total_views"]:,}', _t("pdf.kpi.total_views_channel", "Vues totales (chaîne)"))
    )


def _render_instagram(ig):
    if not ig:
        return f'<p class="no-data">{_t("pdf.nodata.instagram", "Aucune donnée Instagram disponible.")}</p>'
    ig_subs = _t("pdf.kpi.ig_subscribers", "@{username} — Abonnés").format(username=ig["username"])
    summary = _kpi_grid(
        _kpi_card(f'{ig["followers"]:,}', ig_subs)
        + _kpi_card(f'{ig["media_count"]:,}', _t("pdf.kpi.publications", "Publications"))
    )
    # History is shown by the followers line chart above — KPIs only here.
    return summary


def _render_meta(meta):
    if not meta or not meta['campaigns']:
        return f'<p class="no-data">{_t("pdf.nodata.meta", "Aucune donnée Meta Ads disponible.")}</p>'
    summary = _kpi_grid(
        _kpi_card(f'{meta["total_spend"]:,.2f} €', _t("pdf.kpi.total_spend", "Dépenses totales"),
                  val_style="color:#FF4444;")
        + _kpi_card(f'{meta["total_results"]:,}', _t("pdf.kpi.total_results", "Résultats totaux"))
    )
    rows = "".join(
        f"<tr><td>{c[0]}</td><td>{c[1]:,.2f} €</td><td>{c[2]:,}</td>"
        f"<td>{c[3]:,}</td><td>{c[4]:,}</td><td>{c[5]:,.2f} €</td></tr>"
        for c in meta['campaigns'][:5]
    )
    table = _html_table(
        [_t("pdf.col.campaign", "Campagne"), _t("pdf.col.spend", "Dépenses"),
         _t("pdf.col.results", "Résultats"), _t("pdf.col.impressions", "Impressions"),
         _t("pdf.col.reach", "Reach"), _t("pdf.col.cpr", "CPR")], rows)
    return summary + table


def _render_soundcloud_tracks(tracks):
    if not tracks:
        return f'<p class="no-data">{_t("pdf.nodata.soundcloud", "Aucune donnée SoundCloud disponible.")}</p>'
    rows = "".join(
        f"<tr><td>{t[0]}</td><td>{t[1]:,}</td><td>{t[2]:,}</td>"
        f"<td>{t[3]:,}</td><td>{t[4]:,}</td></tr>"
        for t in tracks[:5]
    )
    return _html_table(
        [_t("pdf.col.title", "Titre"), _t("pdf.col.plays", "Plays"),
         _t("pdf.col.likes", "Likes"), _t("pdf.col.reposts", "Reposts"),
         _t("pdf.col.comments", "Commentaires")], rows)


def _render_apple(apple):
    if not apple:
        return f'<p class="no-data">{_t("pdf.nodata.apple", "Aucune donnée Apple Music disponible.")}</p>'
    # KPI only (plays + shazams) — no per-song table (the chart carries the ranking).
    return _kpi_grid(
        _kpi_card(f'{apple["total_plays"]:,}', _t("pdf.kpi.total_plays", "Plays totaux"))
        + _kpi_card(f'{apple["total_shazams"]:,}', _t("pdf.kpi.shazams", "Shazams"))
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
        (_t("pdf.check.revenue_imusician", "Revenu iMusician"),
                                   bool((data.get('roi') or {}).get('revenue_eur'))),
        (_t("pdf.check.ml_predictions", "Prédictions ML"),
                                   bool(data.get('latest_release'))),
        (_t("pdf.check.data_wrapped", "Data Wrapped (saisie)"),
                                   bool(data.get('has_wrapped'))),
    ]
    badge_present = _t("pdf.status.present", "présent")
    badge_empty = _t("pdf.status.empty", "à renseigner / vide")
    rows = "".join(
        f"<tr><td>{name}</td><td>"
        + (f'<span class="badge green">{badge_present}</span>' if ok
           else f'<span class="badge gray">{badge_empty}</span>')
        + "</td></tr>"
        for name, ok in checks
    )
    _h_source = _t("pdf.col.source", "Source")
    _h_status = _t("pdf.col.status", "Statut")
    return (f'<table class="compact"><thead><tr><th>{_h_source}</th><th>{_h_status}</th></tr>'
            f'</thead><tbody>{rows}</tbody></table>')


def _render_hypeddit(hy):
    if not hy:
        return f'<p class="no-data">{_t("pdf.nodata.hypeddit", "Aucune donnée Hypeddit disponible.")}</p>'
    return _kpi_grid(
        _kpi_card(f'{hy["total_visits"]:,}', _t("pdf.kpi.visits_period", "Visites (période)"))
        + _kpi_card(f'{hy["total_clicks"]:,}', _t("pdf.kpi.clicks_period", "Clics (période)"))
    )


def _render_revenue_forecast(rfc):
    if not rfc:
        return f'<p class="no-data">{_t("pdf.nodata.revenue_forecast", "Aucune donnée de revenus pour la projection.")}</p>'
    cards = (
        _kpi_card(f'{rfc["total"]:,.0f} €', _t("pdf.kpi.cumulative_revenue", "Revenu cumulé"))
        + _kpi_card(f'{len(rfc["months"])}', _t("pdf.kpi.months_recorded", "Mois enregistrés"))
    )
    # SACEM royalties shown as a distinct card when present (mirrors the dashboard's
    # per-source SACEM trace on the revenue-forecast view).
    if rfc.get("sacem"):
        cards += _kpi_card(f'{rfc["sacem"]:,.0f} €',
                           _t("pdf.kpi.sacem_royalties", "🎼 Royalties SACEM"))
    return _kpi_grid(cards)


def _render_score20(rows):
    if not rows:
        return f'<p class="no-data">{_t("pdf.nodata.score20", "Score /20 indisponible (lancez `ml_scoring_daily`).")}</p>'
    body = "".join(
        f"<tr><td>{_trunc(s, 42)}</td><td><b>{sc:.1f}</b></td><td>{dw * 100:.0f}%</td>"
        f"<td>{rr * 100:.0f}%</td><td>{ra * 100:.0f}%</td></tr>"
        for s, sc, dw, rr, ra in rows
    )
    note = (f"<p class='subtitle'>{_t('pdf.note.score20', 'Score /20 = classement relatif du catalogue (meilleur = 20, pire = 0) ; pour la proba absolue, lire DW/RR/Radio %.')}</p>")
    return note + _html_table(
        [_t("pdf.col.title", "Titre"), _t("pdf.col.score20", "Score /20"),
         _t("pdf.col.dw_pct", "DW %"), _t("pdf.col.rr_pct", "RR %"),
         _t("pdf.col.radio_pct", "Radio %")], body)


def _render_overview(data):
    """Home-page KPIs: real per-platform totals + IG followers."""
    s = data['streams']
    ig = data.get('instagram') or {}
    return _kpi_grid(
        _kpi_card(f"{s['total']:,}", _t("pdf.kpi.total_streams_all", "Total streams (toutes plateformes)"))
        + _kpi_card(f"{s['s4a']:,}", _t("pdf.kpi.streams_s4a", "Streams Spotify S4A"))
        + _kpi_card(f"{s['youtube']:,}", _t("pdf.kpi.youtube_views", "Vues YouTube"))
        + _kpi_card(f"{s['soundcloud']:,}", _t("pdf.kpi.soundcloud_plays", "Plays SoundCloud"))
        + _kpi_card(f"{s['apple']:,}", _t("pdf.kpi.apple_plays", "Plays Apple Music"))
        + _kpi_card(f"{ig.get('followers', 0):,}" if ig else "—", _t("pdf.kpi.instagram_followers", "Followers Instagram"))
    )


def _render_credentials(creds):
    if not creds:
        return f'<p class="no-data">{_t("pdf.nodata.credentials", "Statut credentials indisponible.")}</p>'
    badge_ok = _t("pdf.cred.configured", "configuré")
    badge_no = _t("pdf.cred.not_configured", "non configuré")
    rows = "".join(
        f"<tr><td>{label}</td><td>"
        + (f'<span class="badge green">{badge_ok}</span>' if ok
           else f'<span class="badge gray">{badge_no}</span>')
        + "</td></tr>"
        for label, ok in creds
    )
    return _html_table([_t("pdf.col.platform", "Plateforme"),
                        _t("pdf.col.credentials", "Credentials")], rows)


def _trunc(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _render_mapping(rows):
    if not rows:
        return f'<p class="no-data">{_t("pdf.nodata.mapping", "Aucun mapping campagne ↔ titre saisi.")}</p>'
    body = "".join(
        f"<tr><td style='width:58%'>{_trunc(c, 46)}</td>"
        f"<td style='width:42%'>{_trunc(t, 34)}</td></tr>"
        for c, t in rows[:15]
    )
    return _html_table([_t("pdf.col.campaign_meta", "Campagne Meta"),
                        _t("pdf.col.title", "Titre")], body)
