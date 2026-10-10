"""R510 — two features left half-done: the NonAlgo gap and the contact without Stripe.

Type: Test
Uses: organic_gap_caption (pure), billing.py source (ast)
Depends on: src/dashboard/views/trigger_algo/_tab_budget_roi.py, src/dashboard/views/billing.py
Persists in: nothing

1. The DW volume threshold showed « not yet collected (Phase 2) » while Saisie S4A had
   collected the non-algo streams since mig. 052: the gap is now computed from the entry.
2. Without Stripe, « contactez-nous » named no one: the message carries a mailto link.

Mutation record (2026-10-11): seen red with the gap computed as `streams - scale`, the
« reached » branch removed, and the `mailto:` dropped from the FR default.
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from src.dashboard.views.trigger_algo._tab_budget_roi import organic_gap_caption

_ROOT = Path(__file__).resolve().parents[1]


def test_the_gap_is_computed_from_the_entry() -> None:
    out = organic_gap_caption((1_200, date(2026, 10, 1)), 5_000)
    assert "**3,800**" in out, out
    assert "Phase 2" not in out


def test_a_reached_threshold_says_so() -> None:
    assert "✅" in organic_gap_caption((6_000, date(2026, 10, 1)), 5_000)


def test_no_entry_names_the_gesture() -> None:
    assert "Saisie S4A" in organic_gap_caption(None, 5_000)


def test_contact_without_stripe_is_a_mailto() -> None:
    tree = ast.parse((_ROOT / "src/dashboard/views/billing.py").read_text(encoding="utf-8"))
    texts = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "t" and n.args
             and getattr(n.args[0], "value", None) == "billing.payment_soon"]
    assert texts, "anti-vacuity: billing.payment_soon is no longer rendered"
    default = "".join(a.value for a in texts[0].args[1:] if isinstance(a, ast.Constant))
    assert "mailto:{email}" in default, "« contactez-nous » without an address to write to"
