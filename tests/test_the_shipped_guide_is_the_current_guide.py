"""Guard: the guide an artist RECEIVES is the guide the code currently describes.

Type: Utility
Uses: pathlib, hashlib (via guide_pdf.source_fingerprint)
Triggers: pytest
Persists in: nothing

Error class `shipped-artifact-lags-its-source`.

Measured 2026-09-03, on the live server.

`docs/guides/onboarding_guide.pdf` was committed 2026-06-13 (`1141d02`) and its
sources last changed 2026-08-30 — **82 days apart**. `/opt/streamlytics/docs/guides/`
on the production host still held both files dated `Jun 13 00:00`. Measured with
`pdftotext`, the shipped PDFs each contained:

    127.0.0.1:8888   x2      (the dead redirect URI R50 deleted)
    Client Secret    x2      (the source now says "one value: your Spotify Artist link")
    Web API          x1      ("Cochez Web API", also deleted)

and the sources contained **zero** of them. Those three strings are exactly the
artist notes « uri non bonne », « rajout de s sur uri », « web api pas cochée ».
They were fixed in the code in June and **were still being delivered** in September.

## Why six existing guards all missed it

`test_a_guide_never_asks_for_a_dead_uri`, `test_the_guide_tells_the_artist_only_what_is_theirs`,
`test_guides_render_per_os`, `test_the_guide_is_fetchable_not_only_mailed`,
`test_the_setup_guide_is_reachable` and `test_guide_pdf` all read the **source**
modules. Not one of them opens `docs/guides/*.pdf`. And the PDF is what
`verification_email._guide_pdf_paths()` attaches to the welcome mail and what both
download buttons serve, straight from a `./docs:/app/docs:ro` bind mount.

The full chain, which is the class: *built by hand -> committed -> rebuilt by no
automation -> rendered by no test -> bind-mounted into the container -> served.*

## Why a fingerprint, and not the two obvious alternatives

**Not the PDF's own bytes.** WeasyPrint is not byte-reproducible across versions
(69.0 here, 68.1 produced the shipped file). A guard that reddens on a dependency
bump gets disabled — `permanently-red-guard-reports-nothing`.

**Not a CI rebuild.** `.github/workflows/ci.yml:62-70` deliberately drops
`libcairo2-dev` ("Removed when PDF stack migrated to WeasyPrint (dashboard-only, not
CI)"), so `build_guide_pdf()` **cannot execute in CI at all**. That is also why
`tests/test_guide_pdf.py` is pure-string. A digest of the rendered HTML is pure
Python and runs everywhere — it is the only guard this environment admits.

See `guide_pdf.source_fingerprint` for why the digest covers the rendered HTML
rather than the content dataclasses, and why `APP_BASE_URL` is normalised out.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.dashboard.guides.guide_pdf import (
    fingerprint_path,
    read_fingerprint,
    rendered_fingerprint,
    source_fingerprint,
)


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


GUIDES = _repo_root() / "docs" / "guides"
REBUILD = "python -m src.dashboard.guides.guide_pdf"


def test_the_fingerprint_file_exists():
    """Without it there is no record of which sources the shipped PDF was built from."""
    fp = fingerprint_path()
    assert fp.is_file(), (
        f"{fp} is missing. It is written by `{REBUILD}` in the same breath as the "
        "PDFs; if it is gone, nothing records which version of the guide sources the "
        "committed PDFs correspond to."
    )


def test_the_shipped_pdfs_match_the_current_sources():
    """Half one: did the guide prose move since the last render?"""
    stored = read_fingerprint().get("source")
    current = source_fingerprint()
    assert stored == current, (
        "the guide sources have changed since the PDFs in docs/guides/ were built.\n"
        f"  stored  (docs/guides/.guide_fingerprint): {stored}\n"
        f"  current (from the guide content modules): {current}\n\n"
        f"Run `{REBUILD}` and commit docs/guides/. This is not cosmetic: the PDF is "
        "attached to every welcome e-mail and served by both download buttons, so a "
        "stale one tells artists to do things the app no longer asks. It happened "
        "for 82 days between 2026-06-13 and 2026-09-03."
    )


def test_the_pdfs_on_disk_are_the_ones_the_fingerprint_certifies():
    """Half two, and the half the first version of this guard was missing.

    Written after the mutation of 2026-09-03: restoring the June PDFs left the
    source-only guard GREEN, because the sources had not moved — only the artefact
    had been swapped. Checking the sources answers "should someone rebuild?"; this
    answers "is what we ship what we last built?". The defect lives in the second
    question, and every one of the six older guards asks a version of the first.
    """
    stored = read_fingerprint().get("rendered")
    current = rendered_fingerprint()
    assert stored == current, (
        "docs/guides/*.pdf are not the files this fingerprint was written for — one "
        "was replaced, restored from an older commit, or rebuilt without updating "
        f"the fingerprint.\n  stored : {stored}\n  on disk: {current}\n\n"
        f"Run `{REBUILD}`, which rewrites both halves together."
    )


@pytest.mark.parametrize("name", ["onboarding_guide.pdf", "onboarding_guide_en.pdf"])
def test_both_language_pdfs_are_present_and_not_empty(name: str):
    """`_guide_pdf_paths()` skips a missing file silently and mails the rest."""
    pdf = GUIDES / name
    assert pdf.is_file(), f"{pdf} is missing — run `{REBUILD}`"
    assert pdf.stat().st_size > 10_000, (
        f"{pdf} is {pdf.stat().st_size} bytes — a truncated render, not a guide"
    )


@pytest.mark.parametrize("dead", ["127.0.0.1:8888", "Client Secret"])
def test_the_rendered_guide_carries_no_string_the_source_has_retired(dead: str):
    """Belt and braces, in the artist's own words.

    The fingerprint above catches ANY drift, including this one. This test names the
    three strings artists actually complained about, so that a future failure says
    *what* an artist will read rather than only *that* a hash moved. It asserts on the
    rendered HTML — the same string the PDF is made of — because reading the PDF back
    would need a parser the suite does not have.
    """
    from src.dashboard.guides.guide_pdf import build_guide_html

    for lang in ("fr", "en"):
        assert dead not in build_guide_html(lang), (
            f"the {lang.upper()} guide renders {dead!r}, which the sources retired in "
            "June 2026. Artist notes: « uri non bonne », « web api pas cochée »."
        )


# ── The welcome mail carries ONE guide, in the reader's language ─────────────

@pytest.mark.parametrize("lang,expected", [("fr", "onboarding_guide.pdf"),
                                           ("en", "onboarding_guide_en.pdf")])
def test_the_welcome_mail_attaches_only_the_readers_guide(lang: str, expected: str):
    """Measured 2026-09-03: every recipient got both PDFs, ~1.5 MB, half unreadable.

    `send_welcome_email` already receives `lang` and uses it for every other string
    in the message; only the attachment ignored it. The plural was introduced on
    2026-06-13 and never narrowed.
    """
    from src.utils.verification_email import _guide_pdf_paths

    paths = _guide_pdf_paths(lang)
    assert len(paths) == 1, f"expected exactly one attachment for {lang!r}, got {paths}"
    assert Path(paths[0]).name == expected


def test_an_unknown_language_still_carries_a_guide():
    """The body says « le guide PDF joint » unconditionally — so one must be there."""
    from src.utils.verification_email import _guide_pdf_paths

    assert [Path(p).name for p in _guide_pdf_paths("de")] == ["onboarding_guide.pdf"]


def test_the_send_path_passes_the_language_through():
    """AST: the call site must forward `lang`, not call the resolver bare.

    Without this the fix is one refactor away from silently reverting to both files —
    `_guide_pdf_paths()` still has a default, so a bare call keeps working.
    """
    import ast

    src = Path(__file__).resolve().parents[1] / "src" / "utils" / "verification_email.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_guide_pdf_paths"]
    assert calls, "_guide_pdf_paths is never called — the welcome mail lost its guide"
    for call in calls:
        assert call.args or call.keywords, (
            f"_guide_pdf_paths() called with no argument at line {call.lineno}: it "
            "falls back to French for every reader, which is the defect this guards."
        )
