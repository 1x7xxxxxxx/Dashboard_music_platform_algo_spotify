"""R248 — « quand la pub sera-t-elle remboursée » counts every euro in and out.

Owner, 2026-09-27, fiche 46: « ajouter la SACEM, tous nos revenus, et nos charges comme le
coût de distribution » ; fiche 62: the distribution cost of a TRACK is entered and summed.
"""
import pandas as pd

from src.dashboard.views.revenue_forecast import cost_label
from src.dashboard.views.trigger_algo._tab_budget_roi import split_ledger


def test_income_is_every_source_and_spend_is_ads_plus_entered_costs():
    cf = pd.DataFrame({
        "year": [2024] * 5, "month": [1, 1, 1, 2, 2],
        "flux": ["revenu", "revenu", "depense", "depense", "depense"],
        "source": ["imusician", "sacem", "meta_ads", "distribution", "mastering"],
        "amount_eur": [10.0, 5.0, 999.0, 20.0, 30.0]})
    meta = pd.DataFrame({"date": pd.to_datetime(["2024-01-03", "2024-01-04"]), "spend": [40.0, 60.0]})
    spend, rev = split_ledger(cf, meta)
    assert rev["revenue_eur"].sum() == 15.0, "SACEM must enter the income"
    assert spend["spend"].sum() == 150.0, (
        "spend = Meta per day (100) + entered costs (50); the monthly Meta line (999) "
        "of the ledger must not be counted a second time")


def test_a_track_names_the_cost_entry():
    assert cost_label("", "Patte Velours", "distribution") == "Distribution — Patte Velours"
    assert cost_label("iMusician", "Patte Velours", "distribution") == "iMusician — Patte Velours"
    assert cost_label("", "—", "mastering") is None


def test_meta_spend_in_decimal_sums_with_entered_costs_in_float():
    """R294 — Postgres NUMERIC arrives as Decimal, the entered costs as float. Summed together
    they raised « Decimal + float » and the chart vanished for every track the day the first
    cost was entered (2026-09-28)."""
    from decimal import Decimal

    import pandas as pd

    from src.dashboard.views.trigger_algo._tab_budget_roi import split_ledger
    cf = pd.DataFrame([{"year": 2024, "month": 3, "flux": "depense", "source": "distribution",
                        "amount_eur": Decimal("30.00")},
                       {"year": 2024, "month": 3, "flux": "revenu", "source": "imusician",
                        "amount_eur": Decimal("12.50")}])
    meta = pd.DataFrame([{"date": "2024-03-01", "spend": Decimal("4.00")},
                         {"date": "2024-03-02", "spend": Decimal("6.00")}])
    spend, rev = split_ledger(cf, meta)
    assert float(spend["spend"].sum()) == 40.0
    assert float(rev["revenue_eur"].sum()) == 12.5
