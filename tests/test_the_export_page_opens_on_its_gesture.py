"""Export CSV: the format choice and « Préparer l'export » head the page (R392).

Type: Guard
Uses: src.dashboard.views.export_csv, tests/render_harness.py (TENANT_SCRIPT)
Depends on: live Postgres for the render (skipped without)
Persists in: nothing

V87 (owner's screen review, 2026-10-05): the page's one gesture — pick ZIP or Excel,
prepare, download — sat under the artist and source settings. It now comes first; the
settings below are pre-filled (every source checked), and the button reads their state.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_WIDGETS = {"radio", "button", "checkbox", "selectbox", "multiselect", "download_button",
            "segmented_control", "button_group", "text_input", "date_input", "toggle"}


def test_an_unchecked_source_leaves_the_export() -> None:
    import streamlit as st

    from src.dashboard.views.export_csv import _SOURCE_GROUPS, _selected_tables

    first = next(iter(_SOURCE_GROUPS))
    st.session_state.clear()
    try:
        assert _selected_tables() == [t for ts in _SOURCE_GROUPS.values() for t in ts]
        st.session_state[f"src_{first}"] = False
        assert not set(_SOURCE_GROUPS[first]) & set(_selected_tables()), (
            "an unchecked source is still exported")
    finally:
        st.session_state.clear()


def _widgets_in_order(node, out: list) -> list:
    for child in getattr(node, "children", {}).values():
        if getattr(child, "type", None) in _WIDGETS:
            out.append(child)
        _widgets_in_order(child, out)
    return out


@pytest.mark.skipif(not db_ready(), reason="renders the export page against the live DB")
def test_the_format_and_the_prepare_button_come_first() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="export_csv",
                                                  artist_id=1))
    at.run(timeout=120)
    assert not at.exception, at.exception
    assert not at.warning, [w.value for w in at.warning]
    first_two = _widgets_in_order(at._tree.main, [])[:2]
    assert [w.type for w in first_two] == ["radio", "button"], (
        f"the page does not open on its gesture: {[(w.type, w.label) for w in first_two]}")
    assert "Préparer" in first_two[1].label

    first_two[1].click()
    at.run(timeout=180)
    assert not at.exception, at.exception
    assert at.session_state["_export_csv_bytes"], "preparing produced no file"
    downloads = [w for w in _widgets_in_order(at._tree.main, [])
                 if w.type == "download_button"]
    assert downloads, "no download button after preparing"
