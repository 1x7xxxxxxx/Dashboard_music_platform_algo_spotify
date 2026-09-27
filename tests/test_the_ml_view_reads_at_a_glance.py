"""R263 (owner note L132) — the ML view: gauges by proximity, the next step per track in €.

Type: Test
Uses: src/dashboard/views/trigger_algo/_release_targets.py (by_proximity),
      src/dashboard/views/trigger_algo/_pareto.py (next_step_rows),
      src/dashboard/views/trigger_algo/_tab_titre.py (one pareto call)

Critic verdicts (critic-2026-09-27.md, R263) : a table of the next step and its € under
the gauges (one algorithm — the nearest gate — and a model-call budget) ; the gauges sorted
by proximity ; no merge of tabs, no « 3 best actions » box (the cost is not computed).

Mutation record (2026-09-27) : `by_proximity` without `reverse=True` → red ; an unpriced
step rendered 0.0 → red ; the second `pareto` call put back in the title tab → red.
"""
import ast
from pathlib import Path

from src.dashboard.views.trigger_algo._pareto import next_step_rows
from src.dashboard.views.trigger_algo._release_targets import by_proximity

ROOT = Path(__file__).resolve().parents[1]


def test_the_closest_track_leads_the_gauges():
    levers = {"far": {("DW", "saves"): {"progress": 0.1}},
              "near": {("RR", "saves"): {"progress": 0.9}},
              "none": {}}
    assert by_proximity(["far", "none", "near"], levers) == ["near", "far", "none"]


def test_the_next_step_carries_its_euros_and_never_invents_them():
    plan = {"algo": "DW", "leviers": [{"label": "Saves", "current": 24, "target": 165,
                                       "unit": "saves", "valeur_eur": None}]}
    rows = next_step_rows([("a", plan, 32.8), ("b", None, None),
                           ("c", {"algo": "RR", "leviers": []}, 9.7)])
    assert [r["song"] for r in rows] == ["a"]
    assert rows[0]["step_eur"] is None and rows[0]["gate_eur"] == 32.8


def test_the_title_tab_replays_the_model_once_not_twice():
    tree = ast.parse((ROOT / "src/dashboard/views/trigger_algo/_tab_titre.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_show_tab_titre")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "pareto"]
    assert len(calls) == 1, f"{len(calls)} appels à pareto — chacun rejoue le modèle"
