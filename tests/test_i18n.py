"""Tests for the dashboard i18n helper — EN→FR→default→key fallback."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard.utils import i18n  # noqa: E402


def _force_lang(monkeypatch, lang):
    monkeypatch.setattr(i18n, "get_lang", lambda: lang)


def test_en_translation_used(monkeypatch):
    _force_lang(monkeypatch, "en")
    assert i18n.t("nav.item.home", "🏠 Accueil") == "🏠 Home"
    assert i18n.t("nav.section.data", "📁 Données") == "📁 Data"


def test_fr_falls_back_to_default_source(monkeypatch):
    # FR has no nav.item.home entry → returns the caller's French default.
    _force_lang(monkeypatch, "fr")
    assert i18n.t("nav.item.home", "🏠 Accueil") == "🏠 Accueil"


def test_missing_key_returns_default_then_key(monkeypatch):
    _force_lang(monkeypatch, "en")
    assert i18n.t("nav.item.does_not_exist", "FR source") == "FR source"
    assert i18n.t("totally.unknown") == "totally.unknown"


def test_ui_key_present_in_both(monkeypatch):
    _force_lang(monkeypatch, "en")
    assert i18n.t("ui.language")  # non-empty
    _force_lang(monkeypatch, "fr")
    assert i18n.t("ui.language")


def test_every_nav_item_key_has_en():
    # Guard: every page key in app._NAV_SECTIONS must have an EN nav.item.* entry,
    # so EN mode never shows a raw French label for a navigation item.
    from src.dashboard.app import _NAV_SECTIONS
    keys = {key for _, _, items in _NAV_SECTIONS for _, key in items}
    en = i18n._TR["en"]
    missing = sorted(k for k in keys if f"nav.item.{k}" not in en)
    assert not missing, f"Missing EN nav translations: {missing}"


# Whole-codebase EN-coverage guard (2026-06-10). The dashboard has ~2300 keys
# across ~47 per-view catalogs; a new `t("ns.key", "FR")` with no EN entry would
# silently render French in EN mode. This locks in the full coverage built during
# the i18n sweep: any new untranslated literal key fails CI.
#
# Static literal calls only — `(?<![A-Za-z0-9_])` avoids matching the trailing `t(`
# of `.get(` / `.getenv(` / `.to_dict(`; the namespaced shape (≥1 dot) excludes
# those false positives; dynamic `t(f"ns.{var}", ...)` keys are skipped (no match).
_T_KEY_RE = re.compile(r'(?<![A-Za-z0-9_])t\(\s*"([a-z][a-z0-9_]*(?:\.[a-zA-Z0-9_]+)+)"')


def test_every_static_t_key_has_en_entry():
    en = i18n._TR["en"]
    dashboard = Path(__file__).resolve().parents[1] / "src" / "dashboard"
    missing: dict[str, list[str]] = {}
    for py in dashboard.rglob("*.py"):
        if py.name == "i18n.py":
            continue  # its module docstring shows an example key (home.total)
        for key in set(_T_KEY_RE.findall(py.read_text(encoding="utf-8"))):
            if key not in en:
                missing.setdefault(py.name, []).append(key)
    assert not missing, (
        "t() keys with no EN catalog entry (would render FR in EN mode): "
        f"{missing}. Add them under src/dashboard/utils/i18n_catalog/."
    )
