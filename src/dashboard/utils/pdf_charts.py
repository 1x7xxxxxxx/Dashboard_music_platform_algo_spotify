"""Matplotlib charts → base64 PNG data URIs for the PDF report.

Type: Sub
Uses: matplotlib (Agg backend — no display), base64
Depends on: s4a_song_timeline, ml_song_predictions (via caller-provided db)
Persists in: nothing

Each builder returns a `data:image/png;base64,…` string ready to drop into an
<img> in the WeasyPrint HTML, or None when there is no data (caller skips it).
Light print theme aligned with the app palette (Spotify green).
"""
import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# pdf_exporter imports pdf_charts lazily (inside functions), and _config imports
# only i18n — so this top-level import introduces no cycle.
from src.dashboard.utils.pdf_exporter._config import _t  # noqa: E402

_GREEN = "#1DB954"
_DARK = "#1a1a2e"
_RED = "#FF4444"
_GREY = "#9aa0a6"
# La palette de l'illustration, celle de l'écran — validée le 2026-09-08 sur les six
# contrôles de contraste. Elle était différente ici (vert/rouge/orange/noir), et les
# deux figures de la page « Vue d'ensemble » donnaient donc DEUX couleurs à chaque
# plateforme : Spotify bleu dans l'évolution, vert dans le bâton juste en dessous.
# Vu en regardant la page, le 2026-09-11.
_PLATFORM_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # Spotify/YT/SC/Apple
_ARTIST_FILTER = "%1x7xxxxxxx%"


def _fig_to_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _style(ax) -> None:
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#dddddd")
    ax.tick_params(colors="#666666", labelsize=8)
    ax.grid(axis="y", color="#eeeeee", linewidth=0.8)
    ax.set_axisbelow(True)


# ── LE DOUBLE AXE : QUAND IL MENT, ET QUAND IL EST LA BONNE FORME ──────────
#
# `platform_chart` s'interdit le double axe et dit pourquoi : deux séries de MÊME
# NATURE d'ampleurs incomparables, posées sur deux échelles choisies par nous, se
# croisent où nous avons décidé qu'elles se croisent. Le lecteur y lit une corrélation
# que la donnée ne porte pas. La forme admissible est alors les petits multiples — une
# facette par série, chacune sur son échelle, l'axe des temps partagé.
#
# Cet interdit ne se transporte PAS mécaniquement au PDF, et c'est ce que R89 demandait
# de trancher. Le critère, écrit une fois :
#
#   • MÊME NATURE (deux comptes du même genre d'événement) → petits multiples.
#     Le double axe y fabrique un croisement, et le croisement est précisément ce que
#     le lecteur vient chercher — « les Shazams précèdent-ils les streams ? ». Des
#     panneaux empilés à axe des temps partagé répondent à la même question sans
#     inventer la réponse.
#
#   • NATURES DIFFÉRENTES (des personnes et des vues, des euros et un coût unitaire,
#     des comptes et un pourcentage) → le double axe reste la forme standard et
#     honnête : il n'existe aucune échelle commune, donc aucun croisement à
#     sur-interpréter. Il est conservé, avec ses libellés d'axe COLORÉS comme la
#     courbe qu'ils décrivent — sans quoi le lecteur ne sait pas quel axe lire.
#
# Balayage du 2026-09-11 — six `twinx()` dans ce fichier, et le tri :
#
#   | figure                   | gauche          | droite              | verdict        |
#   |--------------------------|-----------------|---------------------|----------------|
#   | `apple_daily_growth`     | streams / jour  | shazams / jour      | MÊME → empilé  |
#   | `apple_timeline`         | plays cumulés   | shazams cumulés     | MÊME → empilé  |
#   | `youtube_channel_growth` | abonnés         | vues cumulées       | voir ci-dessous|
#   | `sc_multiaxis`           | écoutes         | likes/reposts/comm. | différent → OK |
#   | `ig_engagement`          | likes, comm.    | taux d'engagement % | différent → OK |
#   | `meta_daily`             | budget €        | résultats           | différent → OK |
#
# `youtube_channel_growth` est le cas que R89 nommait, et il est converti pour une
# raison qui n'est PAS le critère ci-dessus : des abonnés et des vues sont bien de
# natures différentes. Mais la page YouTube du dashboard trace déjà ces deux séries en
# DEUX PANNEAUX EMPILÉS (`make_subplots(rows=2, shared_xaxes=True)`). La même donnée
# prenait donc deux formes dans le même produit, et le PDF est censé être ce que
# l'artiste emporte de l'écran. La cohérence tranche là où le critère ne tranchait pas.


def _ascii_label(label: str) -> str:
    """Le libellé sans son emoji — DejaVu Sans n'en a aucun, et rend un carré vide."""
    return "".join(c for c in label if ord(c) < 0x2190).strip()


def _stacked(n: int, height: float = 3.0):
    """`n` panneaux empilés, axe des temps partagé, chacun sur SON échelle.

    La forme admissible quand deux séries de même nature ont des ampleurs
    incomparables. Le retour est `(fig, axes)` avec `axes` toujours une liste, même
    à `n == 1`.
    """
    fig, axes = plt.subplots(n, 1, sharex=True, figsize=(8.6, height * n * 0.78))
    axes = [axes] if n == 1 else list(axes)
    for ax in axes:
        _style(ax)
    fig.subplots_adjust(hspace=0.22)
    return fig, axes


def streams_timeline(db, artist_id, from_date, to_date, title=None) -> str | None:
    try:
        rows = db.fetch_query(
            """SELECT date, SUM(streams) FROM s4a_song_timeline
               WHERE artist_id = %s AND date BETWEEN %s AND %s AND song NOT ILIKE %s
               GROUP BY date ORDER BY date""",
            (artist_id, from_date, to_date, _ARTIST_FILTER))
    except Exception:
        return None
    rows = [r for r in (rows or []) if r[1] is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    ys = [int(r[1]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.plot(xs, ys, color=_GREEN, linewidth=2)
    ax.fill_between(xs, ys, color=_GREEN, alpha=0.12)
    _style(ax)
    if title is None:
        rng = f"{from_date:%d/%m/%Y} → {to_date:%d/%m/%Y}"
        title = _t("pdf.chart.streams_s4a_range", "Streams S4A — {range}").format(range=rng)
    ax.set_title(title, color=_DARK, fontsize=11, fontweight="bold", loc="left")
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def s4a_cumulative(rows) -> str | None:
    """rows: [(date, daily_streams)] already deduped — plots cumulative area."""
    rows = [(d, int(v or 0)) for d, v in (rows or []) if v is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    cum, acc = [], 0
    for _, v in rows:
        acc += v
        cum.append(acc)
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.plot(xs, cum, color=_GREEN, linewidth=2)
    ax.fill_between(xs, cum, color=_GREEN, alpha=0.12)
    _style(ax)
    ax.set_title(_t("pdf.chart.streams_s4a_cumulative", "Streams S4A cumulés (carrière)"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def s4a_audience_evolution(rows) -> str | None:
    """rows: [(date, listeners, followers)] — two lines over time."""
    rows = [r for r in (rows or []) if r[1] is not None or r[2] is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.plot(xs, [int(r[1] or 0) for r in rows], color=_GREEN, linewidth=2,
            label=_t("pdf.chart.listeners", "Listeners"))
    ax.plot(xs, [int(r[2] or 0) for r in rows], color="#457b9d", linewidth=2,
            label=_t("pdf.chart.followers", "Followers"))
    _style(ax)
    ax.set_title(_t("pdf.chart.s4a_audience", "Audience S4A — listeners & followers"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    ax.legend(fontsize=8, frameon=False)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def song_timeline(rows, song) -> str | None:
    """rows: [(date, streams)] for ONE song — daily streams line."""
    rows = [(d, int(v or 0)) for d, v in (rows or []) if v is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.plot(xs, ys, color=_GREEN, linewidth=2)
    ax.fill_between(xs, ys, color=_GREEN, alpha=0.12)
    _style(ax)
    _song = _short(song, 40)
    ax.set_title(_t("pdf.chart.streams_s4a_song", "Streams S4A — {song}").format(song=_song),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def youtube_channel_growth(rows) -> str | None:
    """rows: [(date, subscribers, views)] — deux panneaux, la forme de l'écran.

    Double axe retiré le 2026-09-11. Pas parce que le critère l'interdisait — des
    abonnés et des vues sont de natures différentes — mais parce que la page YouTube
    du dashboard trace déjà ces deux séries en deux panneaux empilés. La même donnée
    ne prend plus deux formes dans le même produit.
    """
    rows = [r for r in (rows or []) if r[1] is not None or r[2] is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    _subs = _t("pdf.chart.subscribers", "Abonnés")
    _cum_views = _t("pdf.chart.cumulative_views", "Vues cumulées")
    fig, (ax, ax2) = _stacked(2)
    ax.plot(xs, [int(r[1] or 0) for r in rows], color="#FF0000", linewidth=2,
            marker="o", markersize=3)
    ax.set_ylabel(_subs, color="#FF0000", fontsize=8)
    # Trait plein, pas pointillé : le pointillé disait « série secondaire », ce qui
    # avait un sens sur un axe de droite et n'en a plus sur son propre panneau — et
    # c'est la série que le total du produit annonce.
    ax2.plot(xs, [int(r[2] or 0) for r in rows], color="#606060", linewidth=2)
    ax2.set_ylabel(_cum_views, color="#606060", fontsize=8)
    ax.set_title(_t("pdf.chart.youtube_channel_growth", "YouTube — croissance de la chaîne"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def platform_breakdown(streams: dict) -> str | None:
    labels = ["Spotify", "YouTube", "SoundCloud", "Apple"]
    vals = [int(streams.get(k, 0) or 0)
            for k in ("s4a", "youtube", "soundcloud", "apple")]
    if sum(vals) <= 0:
        return None
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    bars = ax.bar(labels, vals, color=_PLATFORM_COLORS, width=0.6)
    _style(ax)
    ax.set_title(_t("pdf.chart.streams_per_platform", "Streams par plateforme"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center",
                va="bottom", fontsize=8, color="#444")
    return _fig_to_uri(fig)


def platform_evolution(series, cumulative, since=None, until=None) -> str | None:
    """La figure phare de l'accueil, dans le PDF — mêmes données, mêmes règles.

    R91 demandait de « donner au PDF les figures pertinentes en partageant la DONNÉE,
    pas le rendu ». L'inventaire du 2026-09-11 a nommé le manque : le PDF portait 25
    figures et **aucune** ne montrait l'évolution multi-plateformes, celle qui ouvre
    l'accueil. Il n'avait que `platform_breakdown`, un bâton par plateforme — des
    totaux, pas une histoire.

    Le rendu ne peut pas être partagé : `kaleido` est absent, donc Plotly → PNG est
    impossible, et c'est la raison pour laquelle ce module existe en matplotlib. Ce
    qui est partagé, c'est tout le reste — et c'est ce qui compte, parce que c'est là
    que vivent les règles :

      * `platform_timeseries.daily_streams_by_platform` et `cumulative_by_platform`
        fournissent les séries, exactement comme à l'écran ;
      * `platform_chart._window`, `_aggregate` et `_as_mode` les mettent en forme —
        donc le report en avant des compteurs, le plancher de seau, et le refus
        d'inventer un jour non mesuré s'appliquent ici sans être réécrits.

    Une règle recopiée diverge : ce dépôt a payé QUATRE copies de « somme des
    compteurs par vidéo », dont trois fausses. Il n'y en a pas de cinquième.

    Importer `platform_chart` amène Streamlit — mais ce module en dépend déjà par
    `_config` → `i18n`, y compris quand le DAG `onboarding_report` produit le PDF.
    Aucune contrainte nouvelle, et seules des fonctions PURES sont appelées.
    """
    from src.dashboard.utils import platform_chart as pc

    if not series:
        return None
    step = "day"
    span, aligned = pc._window(series, None, since, until)
    if span and len(span) > pc._WEEKLY_ABOVE_DAYS:
        step = "week"
        w_since = pc._bucket_key(since, step) if since is not None else None
        w_until = pc._bucket_key(until, step) if until is not None else None
        span, aligned = pc._window(pc._aggregate(series, step, since, until),
                                   None, w_since, w_until, step_days=7)
    if not span or not aligned or len(span) < 2:
        return None

    order, _thin = pc.stackable(span, aligned)
    served = [k for k, rows in (cumulative or {}).items() if rows]
    for key in served:
        aligned.setdefault(key, [None] * len(span))
    order = [k for k in pc.PLATFORM_LABELS
             if k in aligned and (k in order or k in served)]
    if not order:
        return None
    aligned = pc._as_mode(aligned, order, "cumulative", cumulative, span, step)

    # LA QUEUE SE COUPE, elle ne se dessine pas à zéro.
    #
    # Vu en regardant la figure, pas en lisant le code : les trois bandes tombaient à
    # la verticale sur le bord droit. La cause est que le `span` va jusqu'à la
    # dernière mesure de LA PLUS RÉCENTE des plateformes — S4A s'arrêtait le 06-07,
    # YouTube le 06-12 — et qu'un `None` devenu 0 dans un `stackplot` dit « plus
    # aucune écoute » là où il faut dire « plus aucune mesure ». C'est le défaut que
    # `known()` nomme à l'écran, et que l'écran règle en COUPANT la bande.
    #
    # Un `stackplot` ne sait pas couper une bande sans couper les autres. On tronque
    # donc la figure à la dernière date où TOUTES les bandes tracées sont connues.
    # L'autre extrémité n'est pas symétrique et ne se tronque pas : avant sa première
    # mesure, une plateforme valait bien zéro — elle n'était pas encore collectée.
    ends = []
    for key in order:
        seen = [i for i, v in enumerate(aligned[key]) if v is not None]
        if not seen:
            return None
        ends.append(seen[-1])
    last = min(ends)
    if last < 1:
        return None
    span = span[:last + 1]
    stacks = [[v or 0 for v in aligned[k][:last + 1]] for k in order]
    if not any(any(col) for col in stacks):
        return None

    fig, ax = plt.subplots(figsize=(8.6, 3.2))
    # Les libellés portent un emoji, absent de DejaVu Sans : matplotlib le rend en
    # carré vide. Un identifiant à moitié dessiné est un identifiant faux — la
    # légende du PDF prend donc le nom nu.
    ax.stackplot(span, *stacks,
                 colors=[pc._PALETTE_LIGHT[k] for k in order],
                 labels=[_ascii_label(pc.PLATFORM_LABELS[k]) for k in order],
                 linewidth=0.6, edgecolor="white")
    _style(ax)
    ax.set_title(_t("pdf.chart.platform_evolution",
                    "Toutes tes plateformes — évolution cumulée"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    ax.legend(fontsize=8, frameon=False, loc="upper left", ncol=len(order))
    ax.margins(x=0)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def ml_probabilities(db, artist_id, song) -> str | None:
    try:
        row = db.fetch_query(
            """SELECT dw_probability, rr_probability, radio_probability
               FROM ml_song_predictions WHERE artist_id = %s AND song = %s
               ORDER BY prediction_date DESC LIMIT 1""",
            (artist_id, song))
    except Exception:
        return None
    if not row or row[0][0] is None:
        return None
    labels = ["Discover\nWeekly", "Release\nRadar", "Radio"]
    vals = [float(row[0][i] or 0) * 100 for i in range(3)]
    colors = [_GREEN if v >= 50 else ("#FFA500" if v >= 30 else _RED) for v in vals]
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    bars = ax.bar(labels, vals, color=colors, width=0.55)
    ax.set_ylim(0, 100)
    _style(ax)
    # Decision thresholds: <20 STOP, 20-50 OPTIMISER, >=50 SCALER.
    ax.axhline(20, color="#FFA500", linewidth=1, linestyle=":")
    ax.axhline(50, color=_GREEN, linewidth=1, linestyle="--")
    ax.text(2.55, 20, _t("pdf.chart.stop", "STOP"), fontsize=7, color="#FFA500", va="center")
    ax.text(2.55, 50, _t("pdf.chart.scale", "SCALER"), fontsize=7, color=_GREEN, va="center")
    ax.set_title(_t("pdf.chart.algo_probabilities", "Probabilités algorithmes (J+28)"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("%", color="#666", fontsize=8)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}%", ha="center",
                va="bottom", fontsize=9, color="#444", fontweight="bold")
    return _fig_to_uri(fig)


def _short(s, n=24) -> str:
    s = str(s or "—")
    return s if len(s) <= n else s[: n - 1] + "…"


def _hbar(pairs, title, color=_GREEN, unit="") -> str | None:
    """Generic horizontal bar chart from [(label, value), …] (already sorted)."""
    pairs = [(lbl, float(v or 0)) for lbl, v in (pairs or []) if v]
    if not pairs:
        return None
    pairs = pairs[:8][::-1]  # top 8, smallest at bottom for readability
    labels = [_short(p[0]) for p in pairs]
    vals = [p[1] for p in pairs]
    fig, ax = plt.subplots(figsize=(8.6, max(2.2, 0.42 * len(pairs) + 0.8)))
    bars = ax.barh(labels, vals, color=color, height=0.62)
    _style(ax)
    ax.grid(axis="y", linewidth=0)
    ax.grid(axis="x", color="#eeeeee", linewidth=0.8)
    ax.set_title(title, color=_DARK, fontsize=11, fontweight="bold", loc="left")
    for b, v in zip(bars, vals):
        ax.text(v, b.get_y() + b.get_height() / 2, f"  {v:,.0f}{unit}",
                va="center", ha="left", fontsize=8, color="#444")
    ax.margins(x=0.16)
    return _fig_to_uri(fig)


def top_songs_bar(rows, title=None) -> str | None:
    """rows: [(song, value, …)] — bars on value (index 1)."""
    if title is None:
        title = _t("pdf.chart.top_songs_streams", "Top chansons (streams)")
    return _hbar([(r[0], r[1]) for r in (rows or [])], title)


def youtube_top_videos_bar(videos) -> str | None:
    """videos: [(title, date, views, likes, comments)] — bars on views."""
    return _hbar([(v[0], v[2]) for v in (videos or [])],
                 _t("pdf.chart.top_videos_youtube", "Top vidéos YouTube (vues)"),
                 color="#FF0000")


def soundcloud_top_bar(tracks) -> str | None:
    """tracks: [(title, plays, likes, reposts, comments)] — bars on plays."""
    return _hbar([(t[0], t[1]) for t in (tracks or [])],
                 _t("pdf.chart.top_tracks_soundcloud", "Top tracks SoundCloud (plays)"),
                 color="#FF7700")


def meta_campaigns_bar(campaigns) -> str | None:
    """campaigns: [(name, spend, results, impressions, reach, cpr)] — bars on spend."""
    return _hbar([(c[0], c[1]) for c in (campaigns or [])],
                 _t("pdf.chart.spend_per_meta_campaign", "Dépense par campagne Meta Ads"),
                 color=_RED, unit=" €")


def instagram_followers_line(history) -> str | None:
    """history: [(date_str, followers)] over the period."""
    pts = [(d, int(f or 0)) for d, f in (history or []) if f is not None]
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    fig, ax = plt.subplots(figsize=(8.6, 2.8))
    ax.plot(xs, ys, color="#C13584", linewidth=2, marker="o", markersize=3)
    _style(ax)
    ax.set_title(_t("pdf.chart.instagram_followers_evolution", "Évolution des abonnés Instagram"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    step = max(1, len(xs) // 8)
    ax.set_xticks(range(0, len(xs), step))
    ax.set_xticklabels([xs[i] for i in range(0, len(xs), step)], rotation=30, ha="right")
    return _fig_to_uri(fig)


def meta_breakdown_bars(rows, title) -> str | None:
    """rows: [(label, spend)] — horizontal spend bars (country / placement / age)."""
    return _hbar([(r[0], r[1]) for r in (rows or [])], title, color=_RED, unit=" €")


def hypeddit_combo(series) -> str | None:
    """series: [(date_str, visits, clicks)] daily totals."""
    series = [s for s in (series or []) if s[1] is not None]
    if len(series) < 2:
        return None
    xs = [s[0] for s in series]
    visits = [int(s[1] or 0) for s in series]
    clicks = [int(s[2] or 0) for s in series]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.bar(range(len(xs)), visits, color="#7FB3FF", width=0.7,
           label=_t("pdf.chart.visits", "Visites"))
    ax.plot(range(len(xs)), clicks, color=_GREEN, linewidth=2, marker="o",
            markersize=3, label=_t("pdf.chart.clicks", "Clics"))
    _style(ax)
    ax.set_title(_t("pdf.chart.hypeddit_visits_clicks", "Hypeddit — visites & clics"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    step = max(1, len(xs) // 8)
    ax.set_xticks(range(0, len(xs), step))
    ax.set_xticklabels([xs[i] for i in range(0, len(xs), step)], rotation=30, ha="right")
    ax.legend(fontsize=8, frameon=False)
    return _fig_to_uri(fig)


def playlist_adds_bars(windows) -> str | None:
    """windows: {'7d': n, '28d': n, '12m': n} — playlist adds per window."""
    order = [("7d", _t("pdf.chart.window_7d", "7 jours")),
             ("28d", _t("pdf.chart.window_28d", "28 jours")),
             ("12m", _t("pdf.chart.window_12m", "12 mois"))]
    vals = [int((windows or {}).get(k, 0) or 0) for k, _ in order]
    if sum(vals) <= 0:
        return None
    labels = [lbl for _, lbl in order]
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    bars = ax.bar(labels, vals, color=["#9aa0a6", "#1DB954", "#11261a"], width=0.55)
    _style(ax)
    ax.set_title(_t("pdf.chart.playlist_adds", "Ajouts en playlist (S4A)"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center", va="bottom",
                fontsize=9, color="#444", fontweight="bold")
    return _fig_to_uri(fig)


def revenue_forecast_chart(months) -> str | None:
    """months: [(label 'YYYY-MM', revenue)] — bars + linear trend/projection line."""
    months = [(m, float(r or 0)) for m, r in (months or [])]
    if len(months) < 2:
        return None
    labels = [m[0] for m in months]
    vals = [m[1] for m in months]
    n = len(vals)
    # Simple least-squares trend, extended 3 months ahead.
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(vals) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1
    slope = sum((xs[i] - mx) * (vals[i] - my) for i in range(n)) / denom
    intercept = my - slope * mx
    proj_x = list(range(n + 3))
    proj_y = [max(0, slope * x + intercept) for x in proj_x]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.bar(xs, vals, color=_GREEN, width=0.6,
           label=_t("pdf.chart.monthly_revenue", "Revenu mensuel"))
    ax.plot(proj_x, proj_y, color=_RED, linewidth=2, linestyle="--",
            label=_t("pdf.chart.trend_projection_3m", "Tendance + projection 3 mois"))
    _style(ax)
    ax.set_title(_t("pdf.chart.revenue_imusician", "Revenus iMusician & projection"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    step = max(1, len(labels) // 8)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels([labels[i] for i in range(0, len(labels), step)],
                       rotation=30, ha="right")
    ax.legend(fontsize=8, frameon=False)
    return _fig_to_uri(fig)


def indexed_lines(series, title) -> str | None:
    """series: {label: [(x_idx, value)]} — each rebased to 100 at first point."""
    fig, ax = plt.subplots(figsize=(8.6, 3.2))
    plotted = False
    palette = {
        _t("pdf.chart.series.meta_budget", "Budget Meta"): _RED,
        _t("pdf.chart.series.spotify_streams", "Streams Spotify"): _GREEN,
        _t("pdf.chart.series.results", "Résultats"): "#003f5c",
        _t("pdf.chart.series.cpr", "CPR"): "#bc5090",
        _t("pdf.chart.series.popularity", "Popularité"): "#FFA500",
    }
    for label, pts in (series or {}).items():
        pts = [p for p in pts if p[1] is not None]
        if len(pts) < 2 or not pts[0][1]:
            continue
        base = pts[0][1]
        xs = [p[0] for p in pts]
        ys = [p[1] / base * 100 for p in pts]
        ax.plot(xs, ys, linewidth=2, label=label,
                color=palette.get(label, _GREY), marker="o", markersize=2)
        plotted = True
    if not plotted:
        plt.close(fig)
        return None
    _style(ax)
    ax.axhline(100, color="#cccccc", linewidth=0.8, linestyle=":")
    ax.set_title(title, color=_DARK, fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Base 100", color="#666", fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    return _fig_to_uri(fig)


def j28_trajectory(points) -> str | None:
    """points: [(day_index, cumulative_streams)] J0..J+28. Cumulative streams curve only.
    Trigger thresholds are intentionally NOT drawn (they are algo-stream outputs of the
    playlists, not a target on the song's own streams) — explained in the PDF caption."""
    points = [(int(d), int(v or 0)) for d, v in (points or []) if v is not None]
    if len(points) < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    ax.plot(xs, ys, color=_GREEN, linewidth=2.5, marker="o", markersize=3)
    ax.fill_between(xs, ys, color=_GREEN, alpha=0.12)
    _style(ax)
    ax.set_title(_t("pdf.chart.j28_trajectory",
                    "Trajectoire J+28 — streams cumulés depuis la sortie"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    ax.set_xlabel(_t("pdf.chart.days_since_release", "Jours depuis la sortie (J+)"),
                  color="#666", fontsize=8)
    ax.set_ylabel(_t("pdf.chart.cumulative_streams", "Streams cumulés"), color="#666", fontsize=8)
    ax.margins(y=0.12)
    return _fig_to_uri(fig)


def apple_daily_growth(rows) -> str | None:
    """rows: [(date, daily_streams, daily_shazams)] — deux comptes quotidiens, empilés.

    Double axe retiré le 2026-09-11 : deux comptes d'événements du même genre, donc
    deux séries de MÊME NATURE. La question qu'on vient poser à cette figure est « les
    Shazams précèdent-ils les streams ? », et un croisement placé par notre choix
    d'échelles y répondait à notre place.
    """
    rows = [r for r in (rows or []) if r[1] is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    fig, (ax, ax2) = _stacked(2)
    ax.plot(xs, [int(r[1] or 0) for r in rows], color=_GREEN, linewidth=2)
    ax.set_ylabel(_t("pdf.chart.streams_per_day", "Streams / jour"), color=_GREEN, fontsize=8)
    ax2.bar(xs, [int(r[2] or 0) for r in rows], color="#FFA500", alpha=0.6, width=1.0)
    ax2.set_ylabel(_t("pdf.chart.shazams_per_day", "Shazams / jour"), color="#FFA500", fontsize=8)
    ax.set_title(_t("pdf.chart.apple_daily_growth", "Apple Music — croissance quotidienne"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def sc_playback_evolution(rows) -> str | None:
    """rows: [(date, playback_total)] — cumulative plays over time."""
    rows = [(d, int(v or 0)) for d, v in (rows or []) if v is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.plot(xs, [r[1] for r in rows], color="#FF7700", linewidth=2)
    ax.fill_between(xs, [r[1] for r in rows], color="#FF7700", alpha=0.12)
    _style(ax)
    ax.set_title(_t("pdf.chart.soundcloud_plays_evolution", "SoundCloud — évolution des écoutes"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def apple_timeline(rows) -> str | None:
    """rows: [(date, plays_cumul, shazams_cumul)] — deux cumuls de même nature, empilés.

    Double axe retiré le 2026-09-11, même raison qu'`apple_daily_growth` : deux
    cumuls d'événements du même genre. Sur deux échelles choisies par nous, la courbe
    la plus petite peut être dessinée au-dessus de la plus grande.
    """
    rows = [r for r in (rows or []) if r[1] is not None or r[2] is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    _plays_cum = _t("pdf.chart.plays_cumulative", "Plays (cumul)")
    _shazams_cum = _t("pdf.chart.shazams_cumulative", "Shazams (cumul)")
    fig, (ax, ax2) = _stacked(2)
    ax.plot(xs, [int(r[1] or 0) for r in rows], color=_GREEN, linewidth=2,
            marker="o", markersize=4)
    ax.set_ylabel(_plays_cum, color=_GREEN, fontsize=8)
    ax2.plot(xs, [int(r[2] or 0) for r in rows], color="#FFA500", linewidth=2,
             marker="s", markersize=4)
    ax2.set_ylabel(_shazams_cum, color="#FFA500", fontsize=8)
    ax.set_title(_t("pdf.chart.apple_plays_shazams", "Apple Music — plays & shazams (cumul)"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def sc_multiaxis(rows) -> str | None:
    """rows: [(date, plays, likes, reposts, comments)] — plays on left axis, the three
    engagement metrics on a shared right axis (distinct colours, real scales)."""
    rows = [r for r in (rows or []) if r[1] is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.2))
    _plays = _t("pdf.chart.plays", "Écoutes")
    ax.plot(xs, [int(r[1] or 0) for r in rows], color="#FF7700", linewidth=2.4,
            marker="o", markersize=3, label=_plays)
    _style(ax)
    ax.set_ylabel(_plays, color="#FF7700", fontsize=8)
    ax2 = ax.twinx()
    for idx, (lbl, col) in enumerate([(_t("pdf.chart.likes", "Likes"), "#C13584"),
                                      (_t("pdf.chart.reposts", "Reposts"), "#457b9d"),
                                      (_t("pdf.chart.comments", "Commentaires"), "#9d4edd")],
                                     start=2):
        # Drop zero points: SoundCloud likes/reposts were collected as 0 before the
        # client_credentials fix → a 0→real jump that reads as a fake bump.
        pts = [(r[0], int(r[idx] or 0)) for r in rows if int(r[idx] or 0) > 0]
        if len(pts) < 2:
            continue
        ax2.plot([p[0] for p in pts], [p[1] for p in pts], color=col, linewidth=1.8,
                 marker=".", markersize=4, label=lbl)
    ax2.set_ylabel(_t("pdf.chart.engagement_breakdown",
                      "Engagement (likes · reposts · commentaires)"), color="#666", fontsize=8)
    ax2.spines["top"].set_visible(False)
    ax.set_title(_t("pdf.chart.soundcloud_plays_engagement", "SoundCloud — écoutes & engagement"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False, loc="upper left", ncol=2)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def base100_lines(series, title) -> str | None:
    """series: {label: [(date, value)]} — each rebased to 100 at its first point."""
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    colors = ["#FF7700", "#1DB954", "#457b9d", "#9d4edd"]
    plotted = False
    for i, (label, pts) in enumerate(series.items()):
        pts = [(d, float(v)) for d, v in pts if v is not None]
        pts = [p for p in pts if p[1] > 0] or pts
        if len(pts) < 2 or not pts[0][1]:
            continue
        base = pts[0][1]
        ax.plot([p[0] for p in pts], [p[1] / base * 100 for p in pts],
                linewidth=2, label=label, color=colors[i % len(colors)])
        plotted = True
    if not plotted:
        plt.close(fig)
        return None
    _style(ax)
    ax.axhline(100, color="#cccccc", lw=0.8, ls=":")
    ax.set_title(title, color=_DARK, fontsize=11, fontweight="bold", loc="left")
    ax.set_ylabel("Base 100", color="#666", fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def ig_engagement(months) -> str | None:
    """months: [(label, likes, comments, rate_pct)] — stacked engagement + rate line."""
    months = [m for m in (months or [])]
    if len(months) < 1:
        return None
    labels = [m[0] for m in months]
    likes = [int(m[1] or 0) for m in months]
    comments = [int(m[2] or 0) for m in months]
    rates = [float(m[3] or 0) for m in months]
    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    ax.bar(x, likes, color="#C13584", width=0.6, label=_t("pdf.chart.likes", "Likes"))
    ax.bar(x, comments, bottom=likes, color="#F58529", width=0.6,
           label=_t("pdf.chart.comments", "Commentaires"))
    _style(ax)
    ax.set_ylabel(_t("pdf.chart.engagement", "Engagement"), color="#666", fontsize=8)
    ax2 = ax.twinx()
    ax2.plot(x, rates, color="#1DB954", linewidth=2, marker="o", markersize=3,
             label=_t("pdf.chart.rate_pct", "Taux %"))
    ax2.set_ylabel(_t("pdf.chart.engagement_rate_pct", "Taux d'engagement %"),
                   color="#1DB954", fontsize=8)
    ax2.spines["top"].set_visible(False)
    step = max(1, len(labels) // 10)  # thin labels so the axis stays readable
    ax.set_xticks(x[::step])
    ax.set_xticklabels([labels[i] for i in x[::step]], rotation=45, ha="right", fontsize=7)
    ax.set_title(_t("pdf.chart.instagram_monthly_engagement", "Instagram — engagement mensuel"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    return _fig_to_uri(fig)


def meta_funnel(stages) -> str | None:
    """stages: [(label, value)] decreasing — horizontal funnel bars + conv rates."""
    stages = [(lbl, int(v or 0)) for lbl, v in (stages or []) if v]
    if len(stages) < 2:
        return None
    labels = [s[0] for s in stages]
    vals = [s[1] for s in stages]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    y = list(range(len(stages)))[::-1]
    ax.barh(y, vals, color=["#636efa", "#00cc96", "#EF553B", "#1DB954"][:len(stages)],
            height=0.62)
    _style(ax)
    ax.grid(axis="y", lw=0)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    for yi, v in zip(y, vals):
        ax.text(v, yi, f"  {v:,}", va="center", ha="left", fontsize=8, color="#444")
    ax.set_title(_t("pdf.chart.meta_funnel", "Funnel Meta Ads"), color=_DARK, fontsize=11,
                 fontweight="bold", loc="left")
    ax.margins(x=0.15)
    return _fig_to_uri(fig)


def meta_daily(rows) -> str | None:
    """rows: [(date, budget, results, cpr)] — budget bars + CPR line (left, €) +
    results line (right, count)."""
    rows = [r for r in (rows or []) if r[1] is not None]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    _results = _t("pdf.chart.series.results", "Résultats")
    ax.bar(xs, [float(r[1] or 0) for r in rows], color="#FF6B61", alpha=0.4, width=1.0,
           label=_t("pdf.chart.budget_eur", "Budget €"))
    ax.plot(xs, [float(r[3] or 0) for r in rows], color="#bc5090", linewidth=1.5,
            ls="--", marker="o", markersize=2, label=_t("pdf.chart.cpr_eur", "CPR €"))
    _style(ax)
    ax.set_ylabel(_t("pdf.chart.budget_cpr_eur", "Budget / CPR (€)"), color="#666", fontsize=8)
    ax2 = ax.twinx()
    ax2.plot(xs, [int(r[2] or 0) for r in rows], color="#003f5c", linewidth=1.8,
             label=_results)
    ax2.set_ylabel(_results, color="#003f5c", fontsize=8)
    ax2.spines["top"].set_visible(False)
    ax.set_title(_t("pdf.chart.meta_budget_results_cpr", "Meta Ads — budget · résultats · CPR"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False, loc="upper left", ncol=3)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_uri(fig)


def pi_gate(tables, here=None) -> str | None:
    """3-panel bar chart: trigger probability per Popularity-Index bracket per algo."""
    if not tables:
        return None
    brackets = tables.get("pi_brackets", [])
    if not brackets:
        return None
    algos = [("discover_weekly", "Discover Weekly", "#E45756"),
             ("release_radar", "Release Radar", "#4C78A8"),
             ("radio", "Radio", "#54A24B")]
    fig, axes = plt.subplots(1, 3, figsize=(8.6, 2.8))
    # Un panier SANS observation ne se dessine pas.
    #
    # `(data.get(b) or {}).get("prob") or 0` rendait une barre de hauteur zéro pour
    # un panier dont `prob` vaut `null` et `n` vaut 0 — c'est-à-dire un panier où
    # AUCUN titre n'a été observé. Le lecteur y lisait « 0 % de chance », soit
    # l'inverse de « on ne sait pas ». Cas réel dans `threshold_tables.json` :
    # Release Radar, panier « 50+ », n = 0.
    #
    # Et une barre reste une barre, quel que soit ce qui la porte : 66,7 % sur
    # n = 3 s'affichait aussi haut et aussi net que 99,4 % sur n = 172. L'effectif
    # est donc écrit sous chaque barre, et les paniers trop peu peuplés sont
    # atténués. C'est la réponse à « quelle métrique fait foi ? » : la part
    # OBSERVÉE des titres de la cohorte d'entraînement qui ont déclenché cet
    # algorithme-là — trois taux, un par algorithme, chacun avec son effectif.
    _MIN_N = 10
    for ax, (key, label, color) in zip(axes, algos):
        data = tables.get(key, {})
        cells = [(data.get(b) or {}) for b in brackets]
        probs, alphas, counts = [], [], []
        for cell in cells:
            n = int(cell.get("n") or 0)
            prob = cell.get("prob")
            counts.append(n)
            probs.append(float(prob) if (prob is not None and n > 0) else 0.0)
            alphas.append(1.0 if n >= _MIN_N else (0.35 if n > 0 else 0.0))
        edges = ["#111111" if b == here else "none" for b in brackets]
        bars = ax.bar(range(len(brackets)), probs, color=color, edgecolor=edges,
                      linewidth=1.4)
        for bar, alpha in zip(bars, alphas):
            bar.set_alpha(alpha)
        _style(ax)
        ax.set_ylim(0, 100)
        ax.set_title(label, fontsize=9, color=_DARK)
        ax.set_xticks(range(len(brackets)))
        ax.set_xticklabels(
            [f"{b}\nn={n}" if n else f"{b}\n{_t('pdf.chart.no_data', 'n/a')}"
             for b, n in zip(brackets, counts)],
            rotation=45, fontsize=5.5, ha="right")
    fig.suptitle(_t("pdf.chart.pi_gates", "Portes algorithmiques par Popularity Index (%)"),
                 x=0.02, ha="left", fontsize=11, fontweight="bold", color=_DARK)
    fig.text(0.02, 0.90, _t(
        "pdf.chart.pi_gates_caption",
        "Part observée des titres de la cohorte ayant déclenché l'algorithme. "
        "n = nombre de titres ; barre atténuée sous {min_n} titres, « n/a » si aucun."
    ).format(min_n=_MIN_N), ha="left", fontsize=6.5, color="#666")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _fig_to_uri(fig)


def roi_breakeven(roi: dict) -> str | None:
    rev = float(roi.get("revenue_eur") or 0)
    spend = float(roi.get("meta_spend") or 0)
    if rev <= 0 and spend <= 0:
        return None
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    bars = ax.bar([_t("pdf.chart.revenue", "Revenus"), _t("pdf.chart.meta_spend", "Dépenses Meta")],
                  [rev, spend], color=[_GREEN, _RED], width=0.5)
    _style(ax)
    ax.set_title(_t("pdf.chart.roi_revenue_vs_spend", "ROI — Revenus vs Dépenses"),
                 color=_DARK, fontsize=11, fontweight="bold", loc="left")
    for b, v in zip(bars, [rev, spend]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.0f} €", ha="center",
                va="bottom", fontsize=9, color="#444")
    return _fig_to_uri(fig)
