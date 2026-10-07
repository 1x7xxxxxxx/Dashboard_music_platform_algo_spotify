"""SACEM: gross → deductions → net is one waterfall, and the import button opens the tab (R389).

Type: Guard
Uses: src.dashboard.views.sacem, src.dashboard.views.credentials.router, streamlit AppTest
Depends on: live Postgres for the render (skipped without it)
Persists in: nothing

Owner's screen review, 2026-10-05 (V79-V80): the three metric tiles become ONE figure
that reads as a step, not a subtraction; the statement is an .xlsx, said on the page;
and the button lands on the Credentials IMPORT tab, not on the page's first tab.

R461 (owner, 2026-10-07): the SACEM page is now a section of the distributors page,
so the render goes through `imusician` — the alias `sacem` lands there too.
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

    at = _run(AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="imusician",
                                                       artist_id=1)))
    assert any("SACEM" in h.value for h in at.subheader), "the SACEM section is gone"
    # The three SACEM tiles of V79 (gross, net, transfer). The ROI tile above, which
    # names « distrib. + SACEM », belongs to the distributors part and stays.
    tiles = [m.label for m in at.metric if any(k in m.label for k in ("brutes", "Net versé", "viré"))]
    assert not tiles, f"SACEM metric tiles are back: {tiles}"
    assert any(".xlsx" in c.value for c in at.caption), "the .xlsx note is gone"
    buttons = [b for b in at.button if b.key == "sacem_import"]
    assert buttons, "the import button is gone"
    buttons[0].click()
    at.run(timeout=120)
    assert at.session_state["_nav_page"] == "credentials"
    assert at.session_state["_creds_tab"] == CSV_TAB_KEY, (
        "the button opens Credentials, not its import tab")


def test_sacem_is_a_section_of_the_distributors_page() -> None:
    """R461: one menu entry « Distributeur iMusician DistroKid + SACEM »; `sacem` is an alias.

    Mutation record (2026-10-07): the `render_section` call removed from imusician.show
    → red; the alias removed → red.
    """
    import ast
    import inspect

    from src.dashboard.routes import resolve_alias
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    from src.dashboard.views import imusician

    menu = {key for _, _, items in NAV_SECTIONS for _, key in items}
    assert "sacem" not in menu and "imusician" in menu
    assert resolve_alias("sacem")[0] == "imusician"
    show = ast.parse(inspect.getsource(imusician.show))
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "render_section"
               for n in ast.walk(show)), "the SACEM section is no longer rendered"
