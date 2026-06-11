"""Lightweight i18n for the Streamlit dashboard — FR (source/fallback) + EN.

Type: Utility
Persists in: st.session_state['lang']

2-language MVP: a homegrown dict + `t()` helper (zero dependency — gettext/Babel
would be over-sized for two languages). FR is the source of truth AND the fallback:
any key missing in EN renders its FR value (or the `default` passed by the caller),
so partial coverage degrades gracefully (untranslated surfaces stay French).

EN translations live in per-domain catalog modules under i18n_catalog/ (one file
per view: `EN = {key: "..."}`), auto-merged into _TR at import time — parallel
contributors never touch this file. Keys are namespaced `<view>.<slug>`.

Interpolation convention — t() has NO placeholder support; templates use named
`{placeholders}` + `.format()`, NEVER an f-string default (it would freeze the
values before translation):
    st.metric(t("home.total", "Total : {n} titres").format(n=n))

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
        "ui.invalid_session": "Session invalide.",
        "ui.db_unreachable": "❌ Base de données injoignable. Vérifiez que Docker tourne : `docker-compose up -d`",
    },
    "en": {
        "ui.language": "🌐 Langue / Language",
        "nav.title": "🎵 Navigation",
        "ui.invalid_session": "Invalid session.",
        "ui.db_unreachable": "❌ Database unreachable. Make sure Docker is running: `docker-compose up -d`",
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
        "nav.item.meta_mapping": "🔗 Cross-platform mapping",
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


def _load_catalogs() -> None:
    """Merge every i18n_catalog/<module>.EN dict into _TR['en'].

    Best-effort per module: one broken catalog must not take the dashboard down
    (its surface just falls back to French).
    """
    import importlib
    import pkgutil
    try:
        from src.dashboard.utils import i18n_catalog
    except ImportError:
        return
    for mod_info in pkgutil.iter_modules(i18n_catalog.__path__):
        try:
            mod = importlib.import_module(
                f"src.dashboard.utils.i18n_catalog.{mod_info.name}")
            _TR["en"].update(getattr(mod, "EN", {}))
        except Exception:  # noqa: BLE001 — partial coverage beats a crash
            continue


_load_catalogs()


def get_lang() -> str:
    lang = st.session_state.get("lang")
    if lang in _LANGS:
        return lang
    # The login flow calls st.session_state.clear() (MEDIUM-01 session-fixation fix),
    # which would wipe a pre-login choice. Persisting it in the URL lets it survive:
    # re-seed session_state from the ?lang= query param.
    try:
        qp = st.query_params.get("lang")
    except Exception:
        qp = None
    if qp in _LANGS:
        st.session_state["lang"] = qp
        return qp
    return _DEFAULT


def set_lang(lang: str) -> None:
    if lang in _LANGS:
        st.session_state["lang"] = lang
        # Mirror to the URL so the choice survives the login session reset; guard the
        # write (avoids a rerun loop) and tolerate a missing script context (headless).
        try:
            if st.query_params.get("lang") != lang:
                st.query_params["lang"] = lang
        except Exception:
            pass


def translate(key: str, default: str | None = None, lang: str | None = None) -> str:
    """Translate `key` for an EXPLICIT `lang` (default: current session lang).

    Fallback chain EN→FR→default→key, same as `t()`. Decoupled from
    st.session_state so headless/DAG callers (e.g. the PDF exporter) can render in
    a chosen language without a Streamlit script context."""
    lang = lang or get_lang()
    val = _TR.get(lang, {}).get(key)
    if val is not None:
        return val
    fr = _TR.get("fr", {}).get(key)
    if fr is not None:
        return fr
    return default if default is not None else key


def t(key: str, default: str | None = None) -> str:
    """Translate `key` for the current language. Falls back EN→FR→default→key."""
    return translate(key, default, get_lang())


def language_selector(sidebar: bool = True) -> None:
    """Language toggle. Sets st.session_state['lang'] (+ ?lang= URL mirror); the natural
    rerun on change re-renders everything after this in the chosen language.

    sidebar=True renders in the sidebar (in-app shell). sidebar=False renders in the
    current container (pre-login pages, which have no sidebar)."""
    cur = get_lang()
    labels = list(_LANGS)
    container = st.sidebar if sidebar else st
    choice = container.radio(
        t("ui.language"), labels,
        index=labels.index(cur) if cur in labels else 0,
        format_func=lambda c: _LANGS[c], horizontal=True,
        key="_lang_sel" if sidebar else "_lang_sel_pre_login",
        label_visibility="visible")
    set_lang(choice)
