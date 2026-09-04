"""A document that only ever arrives by e-mail is a document one can lose.

R50, from the artist test notes. The onboarding guide PDF was built, attached to the
welcome mail, and offered nowhere in the application. It is the same shape as the
wizard beside it — reachable only through `?page=onboarding`, a link produced solely
in that same mail. Mail closed, tab closed, both gone.

The guard is on REACHABILITY, which is the property that kept failing here and which
a render test cannot see: a page can render perfectly and still be something nobody
can get to.

Moved surface, unchanged question — 2026-09-04
-----------------------------------------------
The two download buttons lived on the welcome step until the artist asked for them
to go: « ça sert à rien, on l'envoie par mail, et sinon je préfère qu'il suive la
page d'onboarding ». That is a decision about WHERE, and this file's question is
about WHETHER — so the assertions follow the guide to the page that still carries
it (📋 Guide de démarrage, a real navigation entry) instead of being deleted along
with the buttons.

Deleting them would have been the easy read and the wrong one: the property that
kept failing here is reachability, and a guard that disappears with the surface it
watched stops watching the property.
"""
from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
ONBOARDING = REPO / "src/dashboard/views/onboarding.py"
GUIDE_PAGE = REPO / "src/dashboard/views/process_guide.py"
SRC = GUIDE_PAGE.read_text(encoding="utf-8")


def test_a_page_in_the_app_offers_the_guide_for_download():
    assert "st.download_button" in SRC, (
        "the onboarding guide is once again e-mail-only — an artist who lost the "
        "welcome mail has no way back to it")
    assert 'mime="application/pdf"' in SRC


def test_that_page_is_reachable_from_the_navigation():
    """Being downloadable somewhere unreachable is the same defect, one level up."""
    app = ast.parse((REPO / "src/dashboard/app.py").read_text(encoding="utf-8"))
    pages = set()
    for node in ast.walk(app):
        if isinstance(node, ast.Assign) and any(
                getattr(x, "id", "") == "_NAV_SECTIONS" for x in node.targets):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    pages.add(sub.value)
    assert "process_guide" in pages, (
        "the page that carries the guide PDF left the navigation — the document "
        "would again be reachable only through the verification e-mail")


def test_the_button_is_wired_to_the_real_builder():
    """A button fed by something other than the shipped guide would drift from it.

    The builder moved on 2026-08-30: `onboarding` now delegates to
    `utils/guide_assets.credentials_guide_pdf`, which is `@st.cache_data`-decorated
    because `process_guide` was rebuilding the same PDF on every rerun (573 ms).
    The question this test asks is unchanged — *is the button fed by the shipped
    guide?* — so the assertion follows the delegation rather than being relaxed to
    whatever onboarding.py still happens to contain.
    """
    assert "credentials_guide_pdf" in SRC, (
        "the guide page no longer reaches the shared guide builder")

    assets = (REPO / "src/dashboard/utils/guide_assets.py").read_text(encoding="utf-8")
    assert "from src.dashboard.guides.guide_pdf import" in assets, (
        "guide_assets no longer imports the real guide builder — the button would "
        "be fed by something that can drift from the shipped document")


def test_a_missing_renderer_degrades_to_no_button_not_a_traceback(monkeypatch):
    """WeasyPrint is optional in some containers, and this is a NEW artist's first
    screen: the failure mode must be a missing button, never a stack trace.

    The cache has to be cleared first, and the reason is worth stating rather than
    working around. Since 2026-08-30 the builder is `@st.cache_data`-decorated, so a
    call that already succeeded in this process returns its bytes without ever
    reaching the patched renderer — the degradation path becomes unobservable. That
    is correct in production (a PDF built once should keep being served) and wrong
    in a test whose entire subject IS that path. CI caught it: the test passed
    serially and failed under `-n auto --dist loadfile`, where an earlier call in the
    same worker had warmed the entry.
    """
    from src.dashboard.utils.guide_assets import credentials_guide_pdf

    credentials_guide_pdf.clear()
    monkeypatch.setattr(
        "src.dashboard.guides.guide_pdf.output_pdf_path",
        lambda lang: (_ for _ in ()).throw(ImportError("no weasyprint")))
    try:
        assert credentials_guide_pdf("fr") is None
    finally:
        # Leave no poisoned entry behind for whatever runs next in this worker.
        credentials_guide_pdf.clear()


def test_the_guide_follows_the_readers_language():
    """Handing an English reader the French PDF is the defect this brick removed.

    Rewritten twice. It first asserted the literal `_guide_pdf_bytes(get_lang())`,
    then `type="primary" if _code == _cur` when the welcome step offered both
    languages side by side. Both were shapes, not the question. Those two buttons
    are gone (2026-09-04); what must still hold is that the surface serving the PDF
    reads the session language rather than assuming one.
    """
    assert "credentials_guide_pdf(lang)" in SRC, (
        "the guide page no longer builds the PDF from a language — every reader "
        "would get the same one")
    assert 'st.session_state.get("lang"' in SRC or "get_lang()" in SRC, (
        "the language handed to the builder is not the reader's own")


def test_the_wizard_is_reachable_from_the_navigation():
    """Not only from the mail. Asserted on `_NAV_SECTIONS`, not on the text of app.py,
    because the deep link kept existing while the entry did not."""
    assert ONBOARDING.exists(), "the wizard file is gone; this guard is blind"
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
