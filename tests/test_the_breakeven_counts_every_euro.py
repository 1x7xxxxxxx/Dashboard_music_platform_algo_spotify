"""R248 — a cost entry names its track (the ledger split left with fiche 51, R553).

Owner, 2026-09-27, fiche 46: « ajouter la SACEM, tous nos revenus, et nos charges comme le
coût de distribution » ; fiche 62: the distribution cost of a TRACK is entered and summed.
"""

from src.dashboard.views.revenue_forecast import cost_label


def test_a_track_names_the_cost_entry():
    assert cost_label("", "Patte Velours", "distribution") == "Distribution — Patte Velours"
    assert cost_label("iMusician", "Patte Velours", "distribution") == "iMusician — Patte Velours"
    assert cost_label("", "—", "mastering") is None
