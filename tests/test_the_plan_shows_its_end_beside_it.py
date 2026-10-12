"""The premium end date sits beside the plan name (R537).

Type: Test
Uses: src.dashboard.utils.premium_end.premium_end_tag, plan_label

Owner, 2026-10-12: « juste à côté de mon plan Premium, entre parenthèses, fin le … ».
A plan that does not end says « sans date de fin » — never an invented date.
"""
from __future__ import annotations

from datetime import datetime

from src.dashboard.utils import premium_end as pe
from src.utils import plan_resolver


def test_a_dated_end_is_written_beside_the_plan(monkeypatch):
    monkeypatch.setattr(plan_resolver, "premium_horizon",
                        lambda db, a: (datetime(2026, 10, 17), "ends"))
    label = pe.plan_label("premium", object(), 18)
    assert label.startswith("Premium (") and "17" in label and "2026" in label


def test_a_granted_plan_says_it_has_no_end(monkeypatch):
    monkeypatch.setattr(plan_resolver, "premium_horizon", lambda db, a: (None, "granted"))
    assert pe.plan_label("premium", object(), 1) == "Premium (sans date de fin)"


def test_free_carries_no_tag():
    assert pe.plan_label("free", object(), 1) == "Free"
    assert pe.premium_end_tag(None, None) is None
