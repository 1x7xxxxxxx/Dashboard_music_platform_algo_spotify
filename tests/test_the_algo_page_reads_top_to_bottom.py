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
    if not at.header:
        pytest.skip("no track to follow in this base — the page stops before its sections")
    return at


pytestmark = pytest.mark.skipif(not db_ready(), reason="renders the algo page against the live DB")


def test_the_page_has_no_tabs_and_its_four_sections_in_order(page) -> None:
    from src.dashboard.views.trigger_algo._sections import section_labels

    assert not page.tabs, f"the algo page draws {len(page.tabs)} tabs again"
    assert [h.value for h in page.header] == section_labels()
    assert len(page.divider) >= len(section_labels()) - 1, "the sections are not separated"


def test_no_table_is_read_outside_a_detail_fold(page) -> None:
    folded = [df for df, anc in _walk(page._tree)
              if type(df).__name__ == "Dataframe" and "Expander" in anc]
    assert len(folded) > 0, "no table rendered at all — the check below would hold on nothing"
    loose = [list(df.value.columns)[:4] for df, anc in _walk(page._tree)
             if type(df).__name__ == "Dataframe" and "Expander" not in anc
             and not df.proto.editing_mode]
    assert not loose, (
        "a read-only table renders outside an expander on the algo page — wrap it in "
        f"`with detail():` (trigger_algo/_sections.py): {loose}")


# ── R404 (V61, V63, V68) ────────────────────────────────────────────────────
# Mutations, 2026-10-05: `_pastilles` call dropped → RED; `MAX_TRACKS = 5` → RED;
# the Groover rate table put back → RED; `_figure_axe` colouring the retained
# setting NEUTRE → RED.

def test_each_playlist_is_a_readable_pill(page) -> None:
    pills = [m.value for m in page.markdown if "-badge[" in m.value]
    assert len(pills) > 0, "no playlist pill on the page"
    for name in ("Discover Weekly", "Radio", "Release Radar"):
        assert any(name in p for p in pills), f"{name} has no pill: {pills}"


def test_the_trigger_values_compare_two_tracks() -> None:
    from src.dashboard.views.trigger_algo._release_targets import MAX_TRACKS

    assert MAX_TRACKS == 2, "V63: « 2 au lieu de 5 »"


def test_budget_shows_no_static_rate_table(page) -> None:
    tables = [list(df.value.columns) for df, _ in _walk(page._tree)
              if type(df).__name__ == "Dataframe"]
    assert len(tables) > 0, "no table at all — the probe sees nothing"
    assert not [c for c in tables if "Coût/soumission (€)" in c], (
        "the Groover/Fluence rate table is back — the rates live in the selector")


def test_the_settings_chart_greens_the_setting_to_keep() -> None:
    import pandas as pd

    from src.dashboard.utils.semantic_colors import BON
    from src.dashboard.views.trigger_algo._tab_reglages import _figure_axe

    df = pd.DataFrame({"valeur": ["LISTEN_NOW", "SANS"], "cpc": [0.12, 0.21],
                       "fiable": [True, True]})
    bar = _figure_axe(df, {"retenir": "LISTEN_NOW"}).data[0]
    assert list(bar.marker.color) == [BON, bar.marker.color[1]]
    assert bar.marker.color[1] != BON
