"""Unit tests — utils.revenue_forecast pure math (extracted in refactor R6).

These cover the forecasting logic that used to be interleaved with Streamlit
rendering in views/revenue_forecast.py and was untestable.
"""
from datetime import datetime

from src.dashboard.utils.revenue_forecast import (
    project_mrr, ltv_global, ltv_scenarios,
)

_JAN = datetime(2026, 1, 1)


class TestProjectMrr:

    def test_zero_growth_is_flat(self):
        r = project_mrr(100.0, 0, 3, start=_JAN)
        assert r['mrr'] == [100.0, 100.0, 100.0, 100.0]
        assert r['arr'] == [1200.0, 1200.0, 1200.0, 1200.0]
        assert r['months'] == ['2026-01', '2026-02', '2026-03', '2026-04']
        assert r['target_month'] is None

    def test_compound_growth(self):
        r = project_mrr(100.0, 10, 2, start=_JAN)
        assert r['mrr'] == [100.0, 110.0, 121.0]

    def test_target_month_is_first_to_reach(self):
        r = project_mrr(100.0, 10, 12, mrr_target=121.0, start=_JAN)
        assert r['target_month'] == 2   # 100 → 110 (M+1) → 121 (M+2)

    def test_target_none_when_unreached(self):
        r = project_mrr(100.0, 1, 3, mrr_target=10_000.0, start=_JAN)
        assert r['target_month'] is None

    def test_enterprise_adds_linear_ramp(self):
        base = project_mrr(0.0, 0, 2, start=_JAN)
        ent = project_mrr(0.0, 0, 2, enterprise_on=True, ent_price=100.0,
                          ent_per_month=1.0, start=_JAN)
        assert base['mrr'] == [0.0, 0.0, 0.0]
        assert ent['mrr'] == [0.0, 100.0, 200.0]


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
