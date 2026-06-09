"""Lightweight i18n for the Streamlit dashboard — FR (source/fallback) + EN.

Type: Utility
Persists in: st.session_state['lang']

2-language MVP: a homegrown dict + `t()` helper (zero dependency — gettext/Babel
would be over-sized for two languages). FR is the source of truth AND the fallback:
any key missing in EN renders its FR value (or the `default` passed by the caller),
so partial coverage degrades gracefully (untranslated surfaces stay French).

Usage:
    from src.dashboard.utils.i18n import t, language_selector
    st.write(t("nav.item.home", "🏠 Accueil"))   # default = the FR source string
"""
import streamlit as st

_DEFAULT = "fr"
_LANGS = {"fr": "🇫🇷 FR", "en": "🇬🇧 EN"}

# FR holds only strings that have no inline `default=` caller (e.g. ui.*). Nav labels
# pass their French source as `default`, so they need no `fr` entry here. EN holds the
# translations added incrementally.
_TR: dict[str, dict[str, str]] = {
    "fr": {
        "ui.language": "🌐 Langue / Language",
        "nav.title": "🎵 Navigation",
    },
    "en": {
        "ui.language": "🌐 Langue / Language",
        "nav.title": "🎵 Navigation",
        # Section headers
        "nav.section.data": "📁 Data",
        "nav.section.analytics": "📊 Platform analytics",
        "nav.section.advanced": "🔮 Spotify algo prediction",
        "nav.section.ads": "📣 Meta Ads advertising",
        "nav.section.revenue": "💶 Revenue",
        "nav.section.reports": "🎁 Data Wrapped",
        "nav.section.account": "👤 Account",
        "nav.section.admin": "🛠️ Admin / Ops",
        # Items (keyed by page key)
        "nav.item.home": "🏠 Home",
        "nav.item.export_pdf": "📄 PDF Export",
        "nav.item.export_csv": "⬇️ CSV Export",
        "nav.item.process_guide": "📋 Getting started",
        "nav.item.credentials": "🔑 API Credentials",
        "nav.item.upload_csv": "📂 CSV Import",
        "nav.item.meta_mapping": "🔗 Spotify × Meta Ads mapping (campaign name)",
        "nav.item.track_mapping": "🧩 Cross-platform mapping",
        "nav.item.db_health": "🗄️ Data health",
        "nav.item.spotify_s4a_combined": "🎵 Spotify & S4A",
        "nav.item.meta_x_spotify": "🎵 Meta × Spotify",
        "nav.item.apple_music": "🎎 Apple Music",
        "nav.item.youtube": "🎬 YouTube",
        "nav.item.soundcloud": "☁️ SoundCloud",
        "nav.item.instagram": "📸 Instagram",
        "nav.item.hypeddit": "📱 Hypeddit",
        "nav.item.saisie_s4a": "📝 S4A entry (playlist & Discovery)",
        "nav.item.trigger_algo": "🚀 Road to Algo (ML)",
        "nav.item.meta_ads_overview": "📱 Overview",
        "nav.item.meta_creatives": "🎨 Creatives",
        "nav.item.meta_breakdowns": "🌍 Meta breakdowns",
        "nav.item.meta_cpr_optimizer": "📊 CPR Optimizer",
        "nav.item.imusician": "💰 Distributor",
        "nav.item.revenue_forecast": "📈 Revenue forecast",
        "nav.item.data_wrapped": "🎁 Data Wrapped",
        "nav.item.account": "👤 My account",
        "nav.item.billing": "💳 Billing",
        "nav.item.referral": "🎁 Referral",
        "nav.item.perf_monitor": "⚡ Dashboard perf.",
        "nav.item.usage_analytics": "📈 Usage Analytics",
        "nav.item.airflow_kpi": "🏗️ ETL monitoring",
        "nav.item.etl_logs": "🗂️ ETL history",
        "nav.item.ml_performance": "🤖 ML model perf.",
        "nav.item.alerts": "🚨 Alerts",
        "nav.item.referral_kpi": "📊 Referral KPIs",
        "nav.item.promo_admin": "🎟️ Promo Codes",
        "nav.item.useful_links": "🔧 Links & tools",
        "nav.item.admin": "⚙️ Admin",
    },
}


def get_lang() -> str:
    return st.session_state.get("lang", _DEFAULT)


def set_lang(lang: str) -> None:
    if lang in _LANGS:
        st.session_state["lang"] = lang


def t(key: str, default: str | None = None) -> str:
    """Translate `key` for the current language. Falls back EN→FR→default→key."""
    val = _TR.get(get_lang(), {}).get(key)
    if val is not None:
        return val
    fr = _TR.get("fr", {}).get(key)
    if fr is not None:
        return fr
    return default if default is not None else key


def language_selector() -> None:
    """Sidebar language toggle. Sets st.session_state['lang']; the natural rerun on
    change re-renders everything (rendered after this) in the chosen language."""
    cur = get_lang()
    labels = list(_LANGS)
    choice = st.sidebar.radio(
        t("ui.language"), labels,
        index=labels.index(cur) if cur in labels else 0,
        format_func=lambda c: _LANGS[c], horizontal=True,
        key="_lang_sel", label_visibility="visible")
    set_lang(choice)
