"""Cross-platform mapping: two expanders one under the other, no tabs (R375).

Type: Guard
Uses: tests/render_harness.py (SCRIPT), tests/db_gate.py
Persists in: nothing

V16 (owner's screen review, 2026-10-05): « Titres et couverture » then « Campagnes Meta »
as two big titles, each in its expander, one under the other — they were two tabs, and
the campaign path hid behind a label. The campaign tab's own sub-tabs (existing / manual
add) became two sections. Streamlit refuses an expander inside an expander, so the
orphans list under « Titres » became a toggle; the render below catches a nested one.

R440 (owner, 2026-10-07): the two « to validate » blocks — title suggestions, then the
automatic campaign suggestions — moved OUT of the expanders, to the top of the page,
« pour identifier les actions à faire directement ». The expanders keep the detail and
open folded.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready
from tests.render_harness import SCRIPT


@pytest.mark.skipif(not db_ready(), reason="renders the mapping page against the live DB")
def test_the_mapping_page_is_two_expanders_in_order() -> None:
    from streamlit.testing.v1 import AppTest

    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.meta_mapping import _load_canonical

    db = get_db_connection()
    try:
        has_reference = bool(_load_canonical(db, 1))
    finally:
        db.close()
    if not has_reference:
        # The CI database has no title reference: the page stops on its « rebuild the
        # reference » notice before either path, so there is no layout to judge.
        pytest.skip("artist 1 has no title reference — the page renders its empty state")

    at = AppTest.from_string(SCRIPT.format(root=os.getcwd(), view="meta_mapping"))
    at.run(timeout=120)
    assert not at.exception, f"meta_mapping raised: {at.exception}"
    assert not at.tabs, f"the mapping page still renders tabs: {[x.label for x in at.tabs]}"
    labels = [e.label for e in at.expander]
    assert len(labels) == 2, f"expected the two paths as expanders, got {labels}"
    assert "Titres" in labels[0] and "Campagnes Meta" in labels[1], (
        f"the titles path must come before the campaigns path: {labels}")

    # R440: the two suggestion blocks are direct children of the page, before the
    # expanders — not inside them.
    top = [getattr(c, "value", "") for c in at.main.children.values()
           if getattr(c, "type", "") != "expander"]
    titles = [i for i, v in enumerate(top) if "suggestions à valider" in str(v)]
    campaigns = [i for i, v in enumerate(top) if str(v).startswith("🤖")]
    assert titles and campaigns and titles[0] < campaigns[0], (
        f"the two « to validate » blocks must open the page, titles first: {top[:8]}")
    for e in at.expander:
        inside = [h.value for h in e.subheader]
        assert not any("suggestions" in h.lower() for h in inside), (
            f"a suggestion block is still folded inside « {e.label} »: {inside}")


def test_nothing_inside_the_two_paths_opens_an_expander() -> None:
    """The render alone cannot see it: the orphans branch is empty on the live data.

    Streamlit raises on an expander inside an expander, and both `_tracks` and
    `_campaigns` render inside one since R375.
    """
    import ast
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views" / "meta_mapping"
    sites = [f"{p.name}:{n.lineno}" for p in pkg.glob("_*.py") if p.name != "__init__.py"
             for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
             if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "expander"]
    assert not sites, f"an expander nested in a mapping path will raise: {sites}"
