"""R489/R514 — when premium falls back to free, in Mon compte AND in Facturation.

Type: Test
Uses: src/utils/plan_resolver.py (premium_end_from_row), src/dashboard/views/account.py,
      src/dashboard/views/billing.py

Owner, 2026-10-09 (W12) : « afficher la date à laquelle le plan premium repasse en free —
dans Mon compte ET dans Facturation / Abonnement ». Premium ends only when EVERY source
granting it ends ; a renewing subscription, a promo without expiry or the legacy tier
has no end, and then no date is shown — a date that is not true is worse than none.

R514 (X12, 2026-10-11) : the line is ALWAYS there while premium is on — the open case
says « sans date de fin » and names its source; a hand grant is not a « welcome trial »;
« Mon plan » leads to Facturation, which carries a primary pay / extend button.

Mutation record (2026-10-11): seen red with the `'granted'` reason renamed, the
`_OPEN` entry for `renews` removed, the pay button dropped from the no-subscription
branch, and the `goto("billing")` call removed.
"""
from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timedelta, timezone

import itertools

from src.dashboard.utils.premium_end import premium_end_sentence
from src.utils.plan_resolver import plan_from_row, premium_end_from_row, premium_horizon_from_row

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


def test_the_open_case_names_its_source():
    assert premium_horizon_from_row(_row(sub="premium", period_end=SOON), NOW) == (None, "renews")
    assert premium_horizon_from_row(_row("premium", None), NOW) == (None, "promo_open")
    assert premium_horizon_from_row(_row(tier="premium"), NOW) == (None, "granted")
    assert premium_horizon_from_row(_row("premium", SOON), NOW) == (SOON, "ends")
    assert premium_horizon_from_row(_row(), NOW) == (None, None)


class _Frozen(datetime):
    """`plan_from_row` reads the wall clock; pin it to NOW (R672 — SOON expired on 2026-10-29)."""

    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)


def test_every_premium_case_gets_a_sentence(monkeypatch):
    """« une phrase de fin de plan dans 100 % des cas premium » — the whole product."""
    monkeypatch.setattr("src.utils.plan_resolver.datetime", _Frozen)
    promos = [(None, None), ("premium", None), ("premium", SOON),
              ("premium", NOW - timedelta(days=1))]
    seen = 0
    for (promo, exp), sub, cancel, tier in itertools.product(
            promos, [None, "premium"], [False, True], ["free", "premium"]):
        row = _row(promo, exp, sub, SOON.replace(tzinfo=None), cancel, tier)
        if plan_from_row((promo, exp, sub, tier)) != "premium":
            assert premium_end_sentence(*premium_horizon_from_row(row, NOW)) is None
            continue
        seen += 1
        sentence = premium_end_sentence(*premium_horizon_from_row(row, NOW))
        assert sentence, f"premium with no end sentence: {row}"
    assert seen >= 20


def test_both_pages_read_the_sentence():
    assert "premium_end_line" in _calls("src/dashboard/views/account.py"), "Mon compte"
    assert "premium_end_line" in _calls("src/dashboard/views/billing.py"), "Facturation"


def test_my_plan_leads_to_billing_and_billing_offers_to_pay():
    account = ast.parse((ROOT / "src/dashboard/views/account.py").read_text(encoding="utf-8"))
    assert any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "goto"
               and [getattr(a, "value", None) for a in c.args] == ["billing"]
               for c in ast.walk(account)), "« Mon plan » does not lead to billing"
    tree = ast.parse((ROOT / "src/dashboard/views/billing.py").read_text(encoding="utf-8"))
    fn = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    calls = {getattr(c.func, "id", getattr(c.func, "attr", ""))
             for c in ast.walk(fn["_show_current_plan"]) if isinstance(c, ast.Call)}
    assert "_render_pay_button" in calls
    no_row = next(n for n in ast.walk(fn["_show_current_plan"])
                  if isinstance(n, ast.If) and ast.unparse(n.test) == "not row")
    assert "_render_pay_button" in ast.unparse(no_row), "the no-subscription case pays too"
    assert 'type="primary"' in ast.unparse(fn["_render_pay_button"]).replace("'", '"')
    assert "essai de bienvenue" not in ast.unparse(no_row), "a hand grant is not a trial"
