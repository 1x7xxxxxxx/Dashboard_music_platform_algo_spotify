"""Treasury page: entry form first, then the one money-flow figure — no tabs (R388, R519).

Type: Guard
Uses: src.dashboard.views.imusician, tests/render_harness.py
Depends on: live Postgres for the render (skipped without)
Persists in: nothing

V75-V78 (owner's screen review, 2026-10-05): the « Données » / « ROI » tabs hid two
readings of one question — does it pay? — from each other, and the detail table said
less than a chart. ONE page now: the entry form on top (the gesture one comes for),
then — since R519 (X11 II) — one figure of the monthly money flow: distributors and SACEM
above zero, Meta Ads below, the running balance as the line.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def _cashflow() -> pd.DataFrame:
    return pd.DataFrame({
        "year":   [2026, 2026, 2026, 2026, 2026],
        "month":  [1, 1, 1, 3, 3],
        "flux":   ["revenu", "revenu", "depense", "revenu", "depense"],
        "source": ["imusician", "sacem", "meta_ads", "imusician", "meta_ads"],
        "amount_eur": [10.0, 5.0, 40.0, 20.0, 15.0],
        "direction": [1, 1, -1, 1, -1]})


def test_the_treasury_is_one_figure_revenue_up_spend_down_balance_as_a_line() -> None:
    """R519 (owner X11 II): distributors, SACEM and Meta Ads on ONE money-flow figure.

    Mutation record (2026-10-11): seen red with the direction dropped (spend drawn
    above zero), the balance not cumulated, barmode « group », and the empty month
    (February) dropped from the axis.
    """
    from src.dashboard.utils.treasury_chart import cashflow_figure

    fig = cashflow_figure(_cashflow())
    bars = {tr.name: list(tr.y) for tr in fig.data if tr.type == "bar"}
    assert set(bars) == {"iMusician", "SACEM", "Publicité Meta"}, bars
    assert bars["Publicité Meta"][0] == -40.0, "a spend is not drawn below zero"
    assert bars["SACEM"][0] == 5.0, "SACEM is not a series of the treasury"
    assert len(bars["iMusician"]) == 3, "a month without movement left the axis"
    (line,) = [tr for tr in fig.data if tr.type == "scatter"]
    assert list(line.y) == [-25.0, -25.0, -20.0], "the balance is not the running sum"
    assert fig.layout.barmode == "relative"
    assert "-20" in fig.layout.title.text and "35" in fig.layout.title.text, fig.layout.title.text


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
    assert any("mois par mois" in h for h in heads), f"the treasury figure is gone: {heads}"
    # R553 (ADR-033, owner Y1) reverses R476: every euro is on this page, the break-even
    # under the treasury, SACEM last.
    point_mort = next((i for i, h in enumerate(heads) if "Point mort" in h), None)
    assert point_mort is not None, f"the break-even is not on the Trésorerie: {heads}"
    assert "SACEM" in heads[-1], f"SACEM is no longer last: {heads}"
    # R488 (W11): « pas de tableaux là où un graphique suffit » — the folded SACEM ledger
    # left too; and the import is a button at the top, not a sentence.
    assert len(at.dataframe) == 0, "a table is back on the distributor page"
    assert any(b.key == "distributor_import" for b in at.button), "the import button is gone"
