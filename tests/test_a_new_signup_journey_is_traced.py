"""R270 (note L5) — the onboarding health page shows where ONE sign-up stands.

Type: Test
Uses: src/dashboard/utils/onboarding_journey.py (stages, journey_line),
      src/dashboard/views/onboarding_health.py

Mutation record (2026-09-27) : the « earlier stage blocks the later ones » rule removed →
red ; the page no longer calling `journey_line` → red.
"""
import ast
from datetime import datetime
from pathlib import Path

from src.dashboard.utils.onboarding_journey import journey_line, stages

ROOT = Path(__file__).resolve().parents[1]


def test_the_stages_follow_the_journey_order():
    d = datetime(2026, 9, 12)
    got = stages((d, True, d, None))
    assert [(n, r) for n, r, _ in got] == [("compte", True), ("mail vérifié", True),
                                          ("identifiants", True), ("première donnée", False)]
    assert journey_line(got).startswith("✅ compte (12/09) → ✅ mail vérifié")


def test_a_later_stage_does_not_count_before_an_earlier_one():
    """A credential typed on an unverified account is not the artist's own journey."""
    d = datetime(2026, 9, 12)
    got = dict((n, r) for n, r, _ in stages((d, False, d, d)))
    assert got == {"compte": True, "mail vérifié": False, "identifiants": False,
                   "première donnée": False}
    assert all(not r for _, r, _ in stages(None))


def test_the_health_page_draws_the_journey():
    tree = ast.parse((ROOT / "src/dashboard/views/onboarding_health.py").read_text(encoding="utf-8"))
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"journey_line", "read_journeys"} <= calls
