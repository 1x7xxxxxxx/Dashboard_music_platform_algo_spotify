"""PDF coverage guard.

Type: Utility
Ensures every artist-facing analytics view in the sidebar (`_NAV_SECTIONS` in
app.py) is reflected by a section in the PDF report (`ALL_SECTIONS` in
pdf_exporter.py). If a new analytics view is added without a PDF section — or a
deliberate exclusion — this test fails, so the report can't silently drift out of
sync with the app.

`_NAV_SECTIONS` is read via AST (no Streamlit import side effects).
"""
import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.dashboard.utils.pdf_exporter import ALL_SECTIONS  # noqa: E402

_APP = _ROOT / "src" / "dashboard" / "app.py"


def _load_const(name):
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} introuvable dans app.py")


# Pages that are NOT analytics reports → out of PDF scope by design.
_NON_ANALYTICS = {
    "home", "export_pdf", "export_csv",            # entry / exports
    "process_guide", "credentials", "upload_csv",  # data setup
    "meta_mapping", "db_health",                   # mapping/management tools
    "account", "billing", "referral",              # account
    "data_wrapped",                                # is itself a recap/report
}

# Analytics view → PDF section key (None = deliberately not a standalone section).
_PDF_MAP = {
    "spotify_s4a_combined": "s4a_songs",
    "meta_x_spotify":       "meta_x_spotify",
    "apple_music":          "apple",
    "youtube":              "youtube",
    "soundcloud":           "soundcloud_detail",
    "instagram":            "instagram",
    "hypeddit":             "hypeddit",
    "trigger_algo":         "songs",
    "meta_ads_overview":    "meta",
    "meta_breakdowns":      "meta_breakdowns",
    "imusician":            "roi",
    "revenue_forecast":     "revenue_forecast",
    # Deliberate exclusions (covered elsewhere or not report-shaped):
    "sacem":                None,   # small account-ledger; royalties already in the ROI section
    "saisie_s4a":           None,   # data-entry form, not a report
    "meta_creatives":       None,   # creative-level detail, summarised by 'meta'
    "meta_cpr_optimizer":   None,   # interactive optimiser tool
}


def _analytics_pages():
    # Exclude the whole "admin" sidebar section by its stable id (robust even if
    # _ADMIN_ONLY is incomplete — e.g. 'alerts' lives there but isn't in the set).
    nav = _load_const("_NAV_SECTIONS")
    keys = {
        key
        for sid, _hdr, items in nav if sid != "admin"
        for _label, key in items
    }
    return keys - _NON_ANALYTICS


def test_every_analytics_view_is_mapped():
    """Each non-admin analytics view must be mapped (to a section or an exclusion)."""
    unmapped = sorted(_analytics_pages() - set(_PDF_MAP))
    assert not unmapped, (
        f"Vues analytics sans section PDF ni exclusion documentée : {unmapped}. "
        f"Ajoute une section dans ALL_SECTIONS + mappe-la dans _PDF_MAP, "
        f"ou marque-la None (exclusion volontaire)."
    )


def test_mapped_sections_exist():
    """Every non-None mapping must point at a real ALL_SECTIONS key."""
    bad = {k: v for k, v in _PDF_MAP.items() if v is not None and v not in ALL_SECTIONS}
    assert not bad, f"Sections PDF inexistantes dans ALL_SECTIONS : {bad}"


def test_no_stale_mapping():
    """_PDF_MAP must not reference views that no longer exist in the nav."""
    nav = _load_const("_NAV_SECTIONS")
    keys = {key for _id, _hdr, items in nav for _label, key in items}
    stale = sorted(set(_PDF_MAP) - keys)
    assert not stale, f"Mappings PDF pointant des vues disparues : {stale}"
