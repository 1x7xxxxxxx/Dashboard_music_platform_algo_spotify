"""A document that only ever arrives by e-mail is a document one can lose.

R50, from the artist test notes. The onboarding guide PDF was built, attached to the
welcome mail, and offered nowhere in the application. It is the same shape as the
wizard beside it — reachable only through `?page=onboarding`, a link produced solely
in that same mail. Mail closed, tab closed, both gone.

The guard is on REACHABILITY, which is the property that kept failing here and which
a render test cannot see: a page can render perfectly and still be something nobody
can get to.
"""
from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
ONBOARDING = REPO / "src/dashboard/views/onboarding.py"
SRC = ONBOARDING.read_text(encoding="utf-8")


def test_the_wizard_offers_the_guide_for_download():
    assert "st.download_button" in SRC, (
        "the onboarding guide is once again e-mail-only — an artist who lost the "
        "welcome mail has no way back to it")
    assert "mime=\"application/pdf\"" in SRC


def test_the_button_is_wired_to_the_real_builder():
    """A button fed by something other than the shipped guide would drift from it."""
    assert "_guide_pdf_bytes" in SRC
    assert "from src.dashboard.guides.guide_pdf import" in SRC


def test_a_missing_renderer_degrades_to_no_button_not_a_traceback(monkeypatch):
    """WeasyPrint is optional in some containers, and this is a NEW artist's first
    screen: the failure mode must be a missing button, never a stack trace."""
    import src.dashboard.views.onboarding as ob

    monkeypatch.setattr(
        "src.dashboard.guides.guide_pdf.output_pdf_path",
        lambda lang: (_ for _ in ()).throw(ImportError("no weasyprint")))
    assert ob._guide_pdf_bytes("fr") is None


def test_the_guide_follows_the_readers_language():
    """The PDF exists in fr and en; handing an English reader the French one is the
    same defect as the stale English guide this brick removed."""
    assert "_guide_pdf_bytes(get_lang())" in SRC


def test_the_wizard_is_reachable_from_the_navigation():
    """Not only from the mail. Asserted on `_NAV_SECTIONS`, not on the text of app.py,
    because the deep link kept existing while the entry did not."""
    app = ast.parse((REPO / "src/dashboard/app.py").read_text(encoding="utf-8"))
    pages = set()
    for node in ast.walk(app):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "_NAV_SECTIONS" for t in node.targets):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    pages.add(sub.value)
    assert pages, "_NAV_SECTIONS not found — this guard is now blind"
    assert "onboarding" in pages, (
        "the setup wizard left the navigation again; it would be reachable only "
        f"through the verification e-mail. Pages found: {sorted(pages)[:12]}…")
