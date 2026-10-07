"""Distributor page: entry form first, then the sales evolution, then break-even — no tabs (R388).

Type: Guard
Uses: src.dashboard.views.imusician, tests/render_harness.py
Depends on: live Postgres for the render (skipped without)
Persists in: nothing

V75-V78 (owner's screen review, 2026-10-05): the « Données » / « ROI » tabs hid two
readings of one question — does it pay? — from each other, and the detail table said
less than a chart. ONE page now: the entry form on top (the gesture one comes for),
the monthly sales stacked per distributor with their running total, then break-even.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def test_the_evolution_stacks_distributors_and_runs_one_total() -> None:
    from src.dashboard.views.imusician import evolution_frame

    df = pd.DataFrame({"year": [2026, 2026, 2026, 2025],
                       "month": [2, 1, 1, 12],
                       "distributor": ["iMusician", "iMusician", "DistroKid", "iMusician"],
                       "revenue_eur": [5.0, 1.0, 2.0, 10.0]})
    evo = evolution_frame(df)
    assert evo["month_start"].is_monotonic_increasing, "the months are not in order"
    by_month = evo.drop_duplicates("month_start").set_index("month_start")["cumulative"]
    assert by_month.tolist() == [10.0, 13.0, 18.0], (
        "the running total does not add every distributor month after month")
    jan = evo[evo["month_start"] == pd.Timestamp("2026-01-01")]
    assert sorted(jan["revenue_eur"].tolist()) == [1.0, 2.0], (
        "a distributor's month was merged into another's bar")


@pytest.mark.skipif(not db_ready(), reason="renders the distributor page against the live DB")
def test_the_page_has_no_tabs_and_starts_with_the_entry_form() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="imusician",
                                                  artist_id=1))
    at.run(timeout=120)
    assert not at.exception, at.exception
    assert len(at.tabs) == 0, "the page is split into tabs again"
    heads = [s.value for s in at.subheader]
    assert heads and "Saisie" in heads[0], f"the entry form is not on top: {heads}"
    evo = next((i for i, h in enumerate(heads) if "Évolution" in h), None)
    roi = next((i for i, h in enumerate(heads) if "Point mort" in h), None)
    assert evo is not None and roi is not None and evo < roi, (
        f"the evolution does not come before break-even: {heads}")
    # R461: the SACEM ledger joined this page, folded in its « Relevé détaillé » expander.
    # The property is « no table SHOWN in place of the chart », not « no table at all ».
    folded = sum(len(e.dataframe) for e in at.expander)
    assert len(at.dataframe) - folded == 0, "the detail table is back in place of the chart"
