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
    """A button fed by something other than the shipped guide would drift from it.

    The builder moved on 2026-08-30: `onboarding` now delegates to
    `utils/guide_assets.credentials_guide_pdf`, which is `@st.cache_data`-decorated
    because `process_guide` was rebuilding the same PDF on every rerun (573 ms).
    The question this test asks is unchanged — *is the button fed by the shipped
    guide?* — so the assertion follows the delegation rather than being relaxed to
    whatever onboarding.py still happens to contain.
    """
    assert "_guide_pdf_bytes" in SRC
    assert "credentials_guide_pdf" in SRC, (
        "onboarding no longer reaches the shared guide builder")

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
    import src.dashboard.views.onboarding as ob
    from src.dashboard.utils.guide_assets import credentials_guide_pdf

    credentials_guide_pdf.clear()
    monkeypatch.setattr(
        "src.dashboard.guides.guide_pdf.output_pdf_path",
        lambda lang: (_ for _ in ()).throw(ImportError("no weasyprint")))
    try:
        assert ob._guide_pdf_bytes("fr") is None
    finally:
        # Leave no poisoned entry behind for whatever runs next in this worker.
        credentials_guide_pdf.clear()


def test_the_guide_follows_the_readers_language():
    """The PDF exists in fr and en; handing an English reader the French one is the
    same defect as the stale English guide this brick removed.

    Rewritten 2026-09-04. It asserted the literal `_guide_pdf_bytes(get_lang())`, and
    went red when the page started offering BOTH languages — a strictly better answer
    to its own question. The predicate matched one implementation, not the question.
    What must hold: both PDFs are offered, and the reader's own language is the one
    put forward.
    """
    assert "_guide_pdf_bytes(_code)" in SRC or "_guide_pdf_bytes(get_lang())" in SRC, (
        "nothing builds the guide PDF from a language any more")
    assert '"fr"' in SRC and '"en"' in SRC, (
        "the two languages are no longer both offered — an artist who reads in one "
        "language cannot hand the guide to someone who reads the other")
    assert 'type="primary" if _code == _cur' in SRC, (
        "the reader's own language is no longer the highlighted button: two equal "
        "buttons make the reader choose something they already told us")


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
