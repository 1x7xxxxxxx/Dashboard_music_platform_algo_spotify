"""Unit tests — utils.revenue_forecast pure math (extracted in refactor R6).

These cover the forecasting logic that used to be interleaved with Streamlit
rendering in views/revenue_forecast.py and was untestable.
"""
from src.dashboard.utils.revenue_forecast import (
    ltv_global, ltv_scenarios,
)


class TestLtvGlobal:

    def test_arpu_over_churn(self):
        assert ltv_global(50.0, 5.0) == 50.0 / 0.05

    def test_zero_churn_returns_zero(self):
        assert ltv_global(50.0, 0) == 0.0


class TestLtvScenarios:

    def test_cartesian_product_and_values(self):
        rows = ltv_scenarios([('basic', 9.90), ('premium', 29.90)], [6, 12])
        assert len(rows) == 4
        assert rows[0] == {'Plan': 'basic', 'Durée (mois)': 6, 'LTV (€)': 59.4}
        assert rows[-1] == {'Plan': 'premium', 'Durée (mois)': 12, 'LTV (€)': 358.8}
