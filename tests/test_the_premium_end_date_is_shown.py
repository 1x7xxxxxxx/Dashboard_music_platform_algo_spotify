"""R489 — the date premium falls back to free, in Mon compte AND in Facturation.

Type: Test
Uses: src/utils/plan_resolver.py (premium_end_from_row), src/dashboard/views/account.py,
      src/dashboard/views/billing.py

Owner, 2026-10-09 (W12) : « afficher la date à laquelle le plan premium repasse en free —
dans Mon compte ET dans Facturation / Abonnement ». Premium ends only when EVERY source
granting it ends ; a renewing subscription, a promo without expiry or the legacy tier
has no end, and then no date is shown — a date that is not true is worse than none.
"""
from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timedelta, timezone

from src.utils.plan_resolver import premium_end_from_row

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
SOON = NOW + timedelta(days=20)
LATER = NOW + timedelta(days=60)


def _row(promo=None, promo_exp=None, sub=None, period_end=None, cancel=False, tier="free"):
    return (promo, promo_exp, sub, period_end, cancel, tier)


def test_an_expiring_promo_ends_on_its_expiry():
    assert premium_end_from_row(_row("premium", SOON), NOW) == SOON


def test_a_renewing_subscription_has_no_end():
    assert premium_end_from_row(_row(sub="premium", period_end=SOON), NOW) is None


def test_a_cancelling_subscription_ends_at_its_period_end():
    # Stripe's period end is a NAIVE timestamp in the database.
    naive = SOON.replace(tzinfo=None)
    assert premium_end_from_row(_row(sub="premium", period_end=naive, cancel=True), NOW) == SOON


def test_the_latest_end_wins_across_sources():
    row = _row("premium", LATER, sub="premium", period_end=SOON.replace(tzinfo=None),
               cancel=True)
    assert premium_end_from_row(row, NOW) == LATER


def test_a_renewing_subscription_outlives_any_promo():
    row = _row("premium", SOON, sub="premium", period_end=LATER, cancel=False)
    assert premium_end_from_row(row, NOW) is None


def test_the_legacy_tier_and_a_promo_without_expiry_have_no_end():
    assert premium_end_from_row(_row(tier="premium"), NOW) is None
    assert premium_end_from_row(_row("premium", None), NOW) is None


def test_free_and_an_expired_promo_have_no_premium_end():
    assert premium_end_from_row(_row(), NOW) is None
    assert premium_end_from_row(_row("premium", NOW - timedelta(days=1)), NOW) is None
    assert premium_end_from_row(None, NOW) is None


def _calls(path: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
            for n in ast.walk(tree) if isinstance(n, ast.Call)}


def test_both_pages_read_the_date():
    assert "premium_end" in _calls("src/dashboard/views/account.py"), "Mon compte"
    assert "premium_end" in _calls("src/dashboard/views/billing.py"), "Facturation"
