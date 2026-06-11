"""Unit tests for the operating-cost expansion engine (no DB, no Streamlit)."""
import datetime as dt

from src.dashboard.utils.app_costs import (
    current_month_cost,
    expand_monthly_costs,
    monthly_total,
)


def _row(**kw):
    base = {
        "category": "vps",
        "amount_eur": 20.0,
        "billing_period": "monthly",
        "start_month": dt.date(2026, 1, 1),
        "end_month": None,
        "active": True,
    }
    base.update(kw)
    return base


class TestExpand:
    def test_monthly_repeats_each_month_to_up_to(self):
        df = expand_monthly_costs([_row()], up_to_month=dt.date(2026, 3, 15))
        # Jan, Feb, Mar — 3 months at 20 €.
        assert list(df["month"]) == [dt.date(2026, 1, 1), dt.date(2026, 2, 1), dt.date(2026, 3, 1)]
        assert df["eur"].tolist() == [20.0, 20.0, 20.0]

    def test_yearly_is_amortised_over_twelve(self):
        df = expand_monthly_costs(
            [_row(category="domain", amount_eur=120.0, billing_period="yearly")],
            up_to_month=dt.date(2026, 2, 1),
        )
        assert df["eur"].tolist() == [10.0, 10.0]  # 120/12

    def test_one_off_lands_on_start_month_only(self):
        df = expand_monthly_costs(
            [_row(category="setup", amount_eur=300.0, billing_period="one_off")],
            up_to_month=dt.date(2026, 4, 1),
        )
        assert len(df) == 1
        assert df.iloc[0]["month"] == dt.date(2026, 1, 1)
        assert df.iloc[0]["eur"] == 300.0

    def test_end_month_bounds_the_series(self):
        df = expand_monthly_costs(
            [_row(end_month=dt.date(2026, 2, 1))],
            up_to_month=dt.date(2026, 6, 1),
        )
        assert list(df["month"]) == [dt.date(2026, 1, 1), dt.date(2026, 2, 1)]

    def test_inactive_row_contributes_nothing(self):
        df = expand_monthly_costs([_row(active=False)], up_to_month=dt.date(2026, 3, 1))
        assert df.empty

    def test_start_after_up_to_is_empty(self):
        df = expand_monthly_costs(
            [_row(start_month=dt.date(2027, 1, 1))], up_to_month=dt.date(2026, 6, 1)
        )
        assert df.empty

    def test_zero_and_missing_amounts_skipped(self):
        df = expand_monthly_costs(
            [_row(amount_eur=0), _row(amount_eur=None)], up_to_month=dt.date(2026, 2, 1)
        )
        assert df.empty

    def test_same_category_same_month_is_summed(self):
        rows = [_row(amount_eur=20.0), _row(amount_eur=5.0)]
        df = expand_monthly_costs(rows, up_to_month=dt.date(2026, 1, 1))
        assert df["eur"].tolist() == [25.0]

    def test_empty_rows_returns_typed_empty_frame(self):
        df = expand_monthly_costs([], up_to_month=dt.date(2026, 1, 1))
        assert df.empty
        assert list(df.columns) == ["month", "category", "eur"]


class TestAggregates:
    def test_monthly_total_sums_categories(self):
        rows = [
            _row(category="vps", amount_eur=20.0),
            _row(category="domain", amount_eur=120.0, billing_period="yearly"),
        ]
        df = expand_monthly_costs(rows, up_to_month=dt.date(2026, 2, 1))
        tot = monthly_total(df)
        assert tot["eur"].tolist() == [30.0, 30.0]  # 20 + 10 each month

    def test_current_month_cost_targets_one_month(self):
        rows = [_row(category="vps", amount_eur=20.0),
                _row(category="claude_code", amount_eur=18.0)]
        assert current_month_cost(rows, dt.date(2026, 5, 10)) == 38.0

    def test_current_month_cost_zero_before_start(self):
        assert current_month_cost([_row(start_month=dt.date(2026, 6, 1))],
                                  dt.date(2026, 1, 1)) == 0.0
