"""R272 (c) — each campaign's settings sit beside what it produced, costs never invented.

Type: Test
Uses: src/dashboard/views/meta_campaign_settings.py (campaign_table)

Mutation record (2026-09-28) : the CPR computed as spend ÷ clicks (not outbound clicks) →
red ; a campaign without outcome dropped by an inner merge → red.
"""
import math

import pandas as pd

from src.dashboard.views.meta_campaign_settings import campaign_table


def test_costs_come_from_the_outcome_and_a_missing_one_stays_absent():
    settings = pd.DataFrame({"campaign_name": ["A", "B"], "daily_budget": [4.0, None],
                             "lifetime_budget": [None, 50.0]})
    outcome = pd.DataFrame({"campaign_name": ["A"], "depense": [100.0], "clics": [400],
                            "clics_sortants": [200]})
    df = campaign_table(settings, outcome).set_index("campaign_name")
    assert list(df.index) == ["A", "B"], "a campaign without outcome is still listed"
    assert df.loc["A", "cpr"] == 0.5 and df.loc["A", "cpc"] == 0.25
    assert math.isnan(df.loc["B", "cpr"]), "no click → absent, never 0"
    assert df.loc["A", "daily_budget"] == 4.0, "budgets are euros, never re-divided"
