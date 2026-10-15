"""R263 (owner note L132) — the ML view: gauges by proximity, the next step per track in €.

Type: Test
Uses: src/dashboard/views/trigger_algo/_release_targets.py (by_proximity)

R570 (2026-10-15) deleted the title tab and its pareto: the « one pareto call » guard
left with the code it guarded.

Critic verdicts (critic-2026-09-27.md, R263) : a table of the next step and its € under
the gauges (one algorithm — the nearest gate — and a model-call budget) ; the gauges sorted
by proximity ; no merge of tabs, no « 3 best actions » box (the cost is not computed).

Mutation record (2026-09-27) : `by_proximity` without `reverse=True` → red ; an unpriced
step rendered 0.0 → red ; the second `pareto` call put back in the title tab → red.
"""
from src.dashboard.views.trigger_algo._release_targets import by_proximity


def test_the_closest_track_leads_the_gauges():
    levers = {"far": {("DW", "saves"): {"progress": 0.1}},
              "near": {("RR", "saves"): {"progress": 0.9}},
              "none": {}}
    assert by_proximity(["far", "none", "near"], levers) == ["near", "far", "none"]
