"""A subscription without a period end renders « — », not a ValueError (R397).

Measured 2026-10-05: a local row with `current_period_end` NULL (left by a Stripe
test-mode session) crashed the admin billing page — pandas turns NULL into NaT, and NaT
is truthy, so `x.strftime(...) if x else "—"` called strftime on it.
"""
from __future__ import annotations

import datetime as _d

from src.dashboard.views.billing import _admin_frame


def test_a_null_period_end_reads_as_a_dash() -> None:
    rows = [("A", "free", None, None, None, None),
            ("B", "premium", "Premium", "active", _d.datetime(2026, 11, 5, 12, 0), "cus_123456789")]
    df = _admin_frame(rows)
    assert df["Period End"].iloc[0] == "—"
    assert "2026" in df["Period End"].iloc[1] and "05" in df["Period End"].iloc[1]
    assert df["Stripe Customer"].tolist() == ["—", "cus_1234…"]
