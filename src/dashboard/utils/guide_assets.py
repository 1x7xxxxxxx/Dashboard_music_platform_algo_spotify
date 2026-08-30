"""Guide PDFs, built once instead of once per Streamlit rerun.

Type: Utility
Uses: streamlit.cache_data, weasyprint (optional), src.dashboard.guides.guide_pdf
Triggers: nothing
Depends on: docs/guides/*.pdf when a pre-rendered copy exists
Persists in: nothing — in-process cache only

Why this module exists
----------------------
`show()` runs again on EVERY widget interaction. A `st.download_button` needs its
payload present at render time, so a naive page builds the file again on each
rerun — expanding an accordion re-renders a PDF nobody asked to download.

Measured in the production container on 2026-08-30:

    573 ms   credentials guide (WeasyPrint, with screenshots)
    148 ms   start guide
    ------
    721 ms   of the 1034 ms `process_guide` spent per rerun

`onboarding.py` already avoided this — its docstring says "WeasyPrint is slow
enough to be felt inside a Streamlit rerun" — and `process_guide.py`, written the
same day for the same reason (R50) and calling the same builder, did not. Two
views, one lesson, applied once. This module is the single place that holds it, so
the next caller inherits the fix instead of re-deriving it.

Why caching is right here and wrong for queries
-----------------------------------------------
ADR-007 rejected `@st.cache_data` on the four heavy views: their cost was SQL
measured under 1 ms, so caching traded freshness for nothing. The cost here is CPU
in a renderer, and the output is a pure function of the language — no tenant data,
nothing to go stale within a session. Different cost, opposite answer. The ADR's
premise is about queries; do not read it as a ban on caching.
"""
from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def credentials_guide_pdf(lang: str) -> bytes | None:
    """The illustrated credentials guide, or None when it cannot be produced here.

    Prefers the copy already rendered under `docs/guides/`; only renders when it is
    absent, because a freshly built container may not carry one. WeasyPrint is an
    optional dependency in some images: a missing one must degrade to "no button",
    never to a traceback on a new artist's first screen.
    """
    try:
        from src.dashboard.guides.guide_pdf import build_guide_pdf, output_pdf_path
        path = output_pdf_path(lang)
        if path.exists():
            return path.read_bytes()
        return build_guide_pdf(lang).read_bytes()
    except Exception as e:  # noqa: BLE001 — an absent guide is not a broken account
        logger.warning("credentials guide PDF unavailable (%s): %s", type(e).__name__, e)
        return None


@st.cache_data(show_spinner=False)
def pdf_from_html(html: str) -> bytes | None:
    """Render `html` to PDF bytes, or None when WeasyPrint is unavailable.

    Keyed on the HTML itself, so a language switch (which changes every `t()` call
    inside the document) produces a different entry rather than a stale one.
    """
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except Exception as e:  # noqa: BLE001 — caller falls back to an HTML download
        logger.warning("PDF rendering unavailable (%s): %s", type(e).__name__, e)
        return None
