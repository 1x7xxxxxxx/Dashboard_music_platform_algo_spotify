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

_GREEN = "#1DB954"
_DARK = "#1a1a2e"
_RED = "#FF4444"
_GREY = "#9aa0a6"
_PLATFORM_COLORS = ["#1DB954", "#FF0000", "#FF7700", "#333333"]  # Spotify/YT/SC/Apple
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


def streams_timeline(db, artist_id, from_date, to_date) -> str | None:
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
    ax.set_title("Évolution des streams (Spotify S4A)", color=_DARK, fontsize=11,
                 fontweight="bold", loc="left")
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
    ax.set_title("Streams par plateforme", color=_DARK, fontsize=11,
                 fontweight="bold", loc="left")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center",
                va="bottom", fontsize=8, color="#444")
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
    ax.set_title("Probabilités algorithmes (J+28)", color=_DARK, fontsize=11,
                 fontweight="bold", loc="left")
    ax.set_ylabel("%", color="#666", fontsize=8)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}%", ha="center",
                va="bottom", fontsize=9, color="#444", fontweight="bold")
    return _fig_to_uri(fig)


def roi_breakeven(roi: dict) -> str | None:
    rev = float(roi.get("revenue_eur") or 0)
    spend = float(roi.get("meta_spend") or 0)
    if rev <= 0 and spend <= 0:
        return None
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    bars = ax.bar(["Revenus", "Dépenses Meta"], [rev, spend],
                  color=[_GREEN, _RED], width=0.5)
    _style(ax)
    ax.set_title("ROI — Revenus vs Dépenses", color=_DARK, fontsize=11,
                 fontweight="bold", loc="left")
    for b, v in zip(bars, [rev, spend]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.0f} €", ha="center",
                va="bottom", fontsize=9, color="#444")
    return _fig_to_uri(fig)
