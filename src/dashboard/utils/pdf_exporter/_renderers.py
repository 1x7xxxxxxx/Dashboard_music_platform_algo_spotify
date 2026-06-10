"""PDF export — renderers layer (move-only split of pdf_exporter)."""
import src.dashboard.utils.pdf_exporter as _pkg



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
