"""Hypeddit: a campaign filter (two latest by default), steps to fetch, history folded (R377).

Type: Guard
Uses: src.dashboard.views.hypeddit, tests/render_harness.py (TENANT_SCRIPT)
Depends on: live Postgres with artist 1's Hypeddit readings for the render (skipped without)
Persists in: nothing

V22-V25 (owner's screen review, 2026-10-05): the entry form stays; an expander « Récupérer
tes chiffres sur Hypeddit » carries the steps; the statistics compare CAMPAIGNS — visits,
clicks and the Meta spend around each release — and default to the two latest releases;
the history is folded by default.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def _has_readings() -> bool:
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        return bool(db.fetch_query(
            "SELECT 1 FROM v_hypeddit_daily WHERE artist_id = 1 LIMIT 1"))
    finally:
        db.close()


@pytest.mark.skipif(not db_ready(), reason="renders the Hypeddit page against the live DB")
def test_the_page_folds_its_history_and_left_the_comparison() -> None:
    if not _has_readings():
        pytest.skip("artist 1 has no Hypeddit reading — the page renders its empty state")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="hypeddit",
                                                  artist_id=1))
    at.run(timeout=120)
    assert not at.exception, at.exception

    # R476 (W5): the campaign comparison left for the cross view's « Mes sorties ».
    assert not [m for m in at.multiselect if "Campagnes" in m.label], (
        "the campaign comparison is back on the Hypeddit page")

    folded = {e.label: e.proto.expanded for e in at.expander}
    history = [label for label in folded if "Historique" in label]
    assert history and not folded[history[0]], f"the history is not folded: {folded}"
    assert any("Récupérer tes chiffres" in label for label in folded), (
        f"the fetch steps are gone: {list(folded)}")
