"""SACEM: gross → deductions → net is one waterfall, and the import button opens the tab (R389).

Type: Guard
Uses: src.dashboard.views.sacem, src.dashboard.views.credentials.router, streamlit AppTest
Depends on: live Postgres for the render (skipped without it)
Persists in: nothing

Owner's screen review, 2026-10-05 (V79-V80): the three metric tiles become ONE figure
that reads as a step, not a subtraction; the statement is an .xlsx, said on the page;
and the button lands on the Credentials IMPORT tab, not on the page's first tab.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def test_the_waterfall_steps_from_gross_to_an_absolute_net() -> None:
    from src.dashboard.views.sacem import gross_to_net_figure

    trace = gross_to_net_figure(1000.0, 180.0, 815.0).data[0]
    assert trace.type == "waterfall"
    assert list(trace.measure) == ["absolute", "relative", "absolute"]
    # The net is its OWN reading, never gross − deductions recomputed by plotly.
    assert list(trace.y) == [1000.0, -180.0, 815.0]


def _run(at):
    at.run(timeout=120)
    assert not at.exception, at.exception
    return at


@pytest.mark.skipif(not db_ready(), reason="renders the SACEM page against the live DB")
def test_the_page_has_no_tiles_and_its_button_opens_the_import_tab() -> None:
    from streamlit.testing.v1 import AppTest

    from src.dashboard.views.credentials.router import CSV_TAB_KEY

    at = _run(AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="sacem",
                                                       artist_id=1)))
    assert not at.metric, f"metric tiles are back: {[m.label for m in at.metric]}"
    assert any(".xlsx" in c.value for c in at.caption), "the .xlsx note is gone"
    buttons = [b for b in at.button if b.key == "sacem_import"]
    assert buttons, "the import button is gone"
    buttons[0].click()
    at.run(timeout=120)
    assert at.session_state["_nav_page"] == "credentials"
    assert at.session_state["_creds_tab"] == CSV_TAB_KEY, (
        "the button opens Credentials, not its import tab")
