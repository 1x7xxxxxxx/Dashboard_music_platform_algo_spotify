"""PDF export — config layer (move-only split of pdf_exporter)."""
import re
from pathlib import Path

from src.dashboard.utils.i18n import translate as _translate

# Render-time language for the PDF, set by render_html(). Deliberately decoupled
# from st.session_state so the exporter renders headless (golden test, future DAG)
# in an explicit language. Default 'fr' keeps the FR golden snapshot byte-identical.
_LANG = {"cur": "fr"}


def _set_lang(lang: str | None) -> None:
    _LANG["cur"] = lang or "fr"


def _t(key: str, default: str) -> str:
    """Translate a PDF string for the current render language (EN→FR→default→key)."""
    return _translate(key, default, _LANG["cur"])


# NB: this module sits one level deeper than the old pdf_exporter.py
# (utils/pdf_exporter/_config.py vs utils/pdf_exporter.py), so the assets path
# needs one extra .parent to still resolve to src/dashboard/assets.
_ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"


def _logo_svg() -> str:
    """Inline the light wordmark SVG for the cover (empty string if missing)."""
    try:
        return (_ASSETS / "logo_horizontal_light.svg").read_text(encoding="utf-8")
    except Exception:
        return ""


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF✀-➿️⭐⬆☁❤]+"
)


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
