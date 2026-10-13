"""The algo page reads top to bottom: no tabs, no raw table outside a detail fold (R403).

Type: Guard
Uses: src.dashboard.views.trigger_algo (render), tests.render_harness.TENANT_SCRIPT
Depends on: live Postgres for the render (skipped without)
Persists in: nothing

Owner's notes V59/V69 (2026-10-05): the four tabs of « Prédiction déclenchement » hid
three quarters of the page behind clicks, and its tables read before its figures. The
page is now four sections separated by a divider, in the order of `PAGE_SECTIONS`, and
every read-only table sits in an expander (`_sections.detail`). An input grid
(`st.data_editor`, the R376 outcome entry) is a form, not a table: it stays in the open.

Mutations, 2026-10-05:
  - `st.tabs(section_labels())` put back in the router → RED (tabs rendered);
  - `with detail():` dropped around the pareto table of « Ce titre » → RED;
  - the editor exemption (`editing_mode`) removed → RED on the two outcome grids,
    which shows the exemption is what lets them through and nothing else.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def _walk(node, ancestors=()):
    for child in getattr(node, "children", {}).values():
        yield child, ancestors
        yield from _walk(child, ancestors + (type(child).__name__,))


@pytest.fixture(scope="module")
def page():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="trigger_algo",
                                                  artist_id=1))
    at.run(timeout=300)
    assert not at.exception, at.exception
    # R525: without a title the page still draws its budget and money sections, so
    # « no header » no longer says « no track » — the no-timeline warning does.
    if not at.header or any("Aucune donnée de timeline" in w.value for w in at.warning):
        pytest.skip("no track to follow in this base — the per-track sections are not drawn")
    return at


pytestmark = pytest.mark.skipif(not db_ready(), reason="renders the algo page against the live DB")


def test_the_page_has_no_tabs_and_its_four_sections_in_order(page) -> None:
    from src.dashboard.views.trigger_algo._sections import section_labels

    assert not page.tabs, f"the algo page draws {len(page.tabs)} tabs again"
    assert [h.value for h in page.header] == section_labels()
    assert len(page.divider) >= len(section_labels()) - 1, "the sections are not separated"


def test_no_table_is_read_on_the_algo_page(page) -> None:
    """R477 (W14) : « pas de tableaux là où un graphique suffit » — 0 table en lecture.

    The editors (`editing_mode`) are inputs, not readings: they stay.
    """
    assert len(list(_walk(page._tree))) > 20, "the page rendered nothing — the check holds on nothing"
    read_only = [list(df.value.columns)[:4] for df, _anc in _walk(page._tree)
                 if type(df).__name__ == "Dataframe" and not df.proto.editing_mode]
    assert not read_only, f"a read-only table renders on the algo page: {read_only}"


# ── R404 (V61, V63, V68) ────────────────────────────────────────────────────
# Mutations, 2026-10-05: `_pastilles` call dropped → RED; `MAX_TRACKS = 5` → RED;
# the Groover rate table put back → RED. (The settings chart moved to the cross view,
# R557 — its guard is tests/test_the_best_settings_tool_ranks_every_setting.py.)

def test_each_playlist_is_a_readable_pill(page) -> None:
    pills = [m.value for m in page.markdown if "-badge[" in m.value]
    assert len(pills) > 0, "no playlist pill on the page"
    for name in ("Discover Weekly", "Radio", "Release Radar"):
        assert any(name in p for p in pills), f"{name} has no pill: {pills}"


def test_the_trigger_values_compare_two_tracks() -> None:
    from src.dashboard.views.trigger_algo._release_targets import MAX_TRACKS

    assert MAX_TRACKS == 2, "V63: « 2 au lieu de 5 »"
