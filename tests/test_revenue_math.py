"""ROI math — get_roi_data computes the profitability number artists act on.

Only exercised indirectly via the PDF golden (which feeds a hardcoded roi dict), so the
TRUE ROI computation was untested. A sign/denominator regression would mis-report
profitability with plausible-looking numbers. DB-free: a stubbed handler returns known
revenue + spend rows. get_roi_data is @st.cache_data — clear() before each assert so the
underscore-_db (unhashable, not keyed) doesn't serve a stale result across cases.
"""
from datetime import date
from unittest.mock import MagicMock

from src.dashboard.utils.kpi_helpers import get_roi_data


def _stub_db(revenue, spend):
    db = MagicMock()
    # get_roi_data issues two fetch_query calls in order: revenue, then meta spend.
    db.fetch_query.side_effect = [[(revenue,)], [(spend,)]]
    return db


def test_true_roi_profitable():
    get_roi_data.clear()
    r = get_roi_data(_stub_db(210.5, 80.0), 1, date(2020, 1, 1), date(2026, 1, 1))
    assert r["revenue_eur"] == 210.5
    assert r["meta_spend"] == 80.0
    assert r["total_spend"] == 80.0  # Hypeddit excluded — Meta only
    assert round(r["roi_pct"], 2) == round((210.5 - 80.0) / 80.0 * 100, 2)
    assert r["profitable"] is True


def test_true_roi_deficit_is_negative():
    get_roi_data.clear()
    r = get_roi_data(_stub_db(40.0, 100.0), 1, date(2020, 1, 1), date(2026, 1, 1))
    assert r["roi_pct"] < 0  # spent more than earned → real loss, not a +ratio
    assert r["profitable"] is False


def test_zero_spend_leaves_roi_undefined():
    get_roi_data.clear()
    r = get_roi_data(_stub_db(50.0, 0.0), 1, date(2020, 1, 1), date(2026, 1, 1))
    # No spend → ROI is undefined (no division), not 0 or infinity.
    assert r["roi_pct"] is None
    assert r["profitable"] is False
