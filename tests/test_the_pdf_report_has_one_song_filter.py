"""Career PDF form: three filters on one row, then the button, one song list (R386).

Type: Guard
Uses: src.dashboard.views.export_pdf, src.dashboard.utils.nav_sections
Depends on: live Postgres (skipped without) — the form reads the artist's songs
Persists in: nothing

V47-V51 (owner's screen review, 2026-10-05): the report sat behind two song pickers —
« S4A — chansons à inclure » and « Focus ML — chansons à inclure » — which could name
two different sets of titles in one document. ONE « Chansons » filter now sits beside
Artiste and Période, empty meaning the whole catalogue, with a « dernière sortie »
shortcut; « Générer » follows the three filters; « Rapport pour … » is gone.

`generate_pdf` is replaced inside the rendered script by a recorder: what matters here
is what the form HANDS the generator — the PDF's own sections are covered by
`test_pdf_coverage.py`.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["authenticated"] = True
import src.dashboard.views.export_pdf as v
def _record(db, **kw):
    st.session_state["_handed"] = kw
    return b"%PDF-1.4"
_original = v.generate_pdf
v.generate_pdf = _record
try:
    v.show()
finally:
    v.generate_pdf = _original
"""


def _app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd()))
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


def _songs(at):
    pickers = [m for m in at.multiselect if m.label == "Chansons"]
    assert len(pickers) == 1, (
        f"expected ONE song filter, got {[m.label for m in at.multiselect]}")
    return pickers[0]


def _flat(node):
    for c in getattr(node, "children", {}).values():
        yield c
        yield from _flat(c)


def test_three_filters_on_one_row_then_the_button() -> None:
    at = _app()
    rows = [n for n in _flat(at._tree)
            if [type(k).__name__ for k in getattr(n, "children", {}).values()]
            == ["Column"] * 3]
    assert rows, "no row of three columns — the filters are not side by side"
    first = rows[0]
    heads = " ".join(getattr(x, "value", "") or "" for x in _flat(first)
                     if getattr(x, "type", "") == "markdown")
    for word in ("Artiste", "Période", "Chansons"):
        assert word in heads, f"« {word} » is not in the first three-column row: {heads}"

    order = [x for x in _flat(at._tree)
             if getattr(x, "type", "") in ("button", "checkbox")]
    kinds = [(x.type, getattr(x, "label", "")) for x in order]
    gen = next(i for i, (k, lbl) in enumerate(kinds) if k == "button" and "Générer" in lbl)
    first_box = next(i for i, (k, _) in enumerate(kinds) if k == "checkbox")
    assert gen < first_box, f"« Générer » comes after the section boxes: {kinds}"
    assert not any("Rapport pour" in (c.value or "") for c in at.caption), (
        "« Rapport pour … » is back")


def test_all_songs_feed_both_song_sections_the_same_titles() -> None:
    at = _app()
    picker = _songs(at)
    if not picker.options:
        pytest.skip("the first artist has no S4A song — nothing to hand over")
    assert picker.value == [], "the song filter does not default to « toutes »"
    next(b for b in at.button if "Générer" in b.label).click().run(timeout=120)
    assert not at.exception, at.exception
    kw = at.session_state["_handed"]
    assert kw["s4a_songs_filter"] is None, "« toutes » filtered the S4A table"
    if kw["sections"].get("songs"):
        assert kw["songs"] == list(picker.options), (
            "the ML focus does not cover the catalogue the S4A table is drawn from")


def test_the_latest_release_button_narrows_both_sections() -> None:
    at = _app()
    picker = _songs(at)
    latest = next(b for b in at.button if "Dernière sortie" in b.label)
    if latest.disabled:
        pytest.skip("no known latest release among the first artist's songs")
    latest.click().run(timeout=90)
    chosen = _songs(at).value
    assert len(chosen) == 1 and chosen[0] in picker.options, chosen
    next(b for b in at.button if "Générer" in b.label).click().run(timeout=120)
    kw = at.session_state["_handed"]
    assert kw["s4a_songs_filter"] == chosen
    if kw["sections"].get("songs"):
        assert kw["songs"] == chosen
