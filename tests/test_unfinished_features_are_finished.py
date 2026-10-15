"""R510 — a feature left half-done: the contact without Stripe.

Type: Test
Uses: billing.py source (ast)
Depends on: src/dashboard/views/billing.py
Persists in: nothing

Without Stripe, « contactez-nous » named no one: the message carries a mailto link.
(R510's NonAlgo-gap half lived in the Budget & ROI tab, removed by R570.)

Mutation record (2026-10-11): seen red with the `mailto:` dropped from the FR default.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_contact_without_stripe_is_a_mailto() -> None:
    tree = ast.parse((_ROOT / "src/dashboard/views/billing.py").read_text(encoding="utf-8"))
    texts = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "t" and n.args
             and getattr(n.args[0], "value", None) == "billing.payment_soon"]
    assert texts, "anti-vacuity: billing.payment_soon is no longer rendered"
    default = "".join(a.value for a in texts[0].args[1:] if isinstance(a, ast.Constant))
    assert "mailto:{email}" in default, "« contactez-nous » without an address to write to"
