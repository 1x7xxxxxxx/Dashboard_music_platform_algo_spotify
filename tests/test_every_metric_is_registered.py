"""Every gold object a surface reads is a REGISTERED metric (R231, 2026-09-27).

Type: Test
Uses: src/utils/metric_registry.py, tools/dev/gold_coverage.py (scan_sql, tests_naming)
Depends on: migrations/*.sql, tests/
Persists in: nothing

The owner: « une métrique = une définition canonique = une source de vérité ». The
registry holds what exists nowhere else (definition, grain, SENSE, window); this test
holds the registry to the code: no gold object read by the product without an entry, no
entry pointing at an object that no longer exists, and the metrics with no quality test
at all can only become fewer.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

# Measured 2026-09-27: 4 metrics named by no test (active_budget, campaign_track, costs,
# spotify_popularity). A ceiling: it goes down, never up.
_UNTESTED_CEILING = 4


def _registry():
    spec = importlib.util.spec_from_file_location("metric_registry_t",
                                                  ROOT / "src/utils/metric_registry.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _gold():
    import gold_coverage as gc
    gold, *_ = gc.analyse()
    return gc, gold


def test_every_read_gold_object_is_registered_and_no_entry_is_dead() -> None:
    reg = _registry()
    gc, gold = _gold()
    unregistered = sorted(n for n, g in gold.items() if g.consumers and n not in reg.REGISTRY)
    dead = sorted(n for n in reg.REGISTRY if n not in gold)
    assert sum(1 for g in gold.values() if g.consumers) >= 20, (
        "the analysis found almost no consumer — the guard would pass on anything")
    assert not unregistered, f"gold objects read by the product with no metric entry: {unregistered}"
    assert not dead, f"registry entries whose gold object no longer exists: {dead}"


def test_every_metric_says_its_sense() -> None:
    reg = _registry()
    allowed = {reg.FLUX, reg.CUMUL, reg.NIVEAU, reg.ATTRIBUT}
    bad = [m.name for m in reg.REGISTRY.values() if m.sense not in allowed]
    assert not bad, f"a metric without a valid sense (flux/cumul/niveau/attribut): {bad}"
    names = [m.name for m in reg.REGISTRY.values()]
    assert len(names) == len(set(names)), "two gold objects registered under ONE metric name"


def test_every_metric_carries_its_whole_card() -> None:
    """REQ-GOLD-02 — definition, formula, grain, window: an empty field is a card with a hole.

    The previous proof only capped untested metrics; emptying a formula stayed green
    (mutated 2026-10-04, R364).
    """
    reg = _registry()
    holes = {m.name: f for m in reg.REGISTRY.values()
             for f in ("definition", "formula", "grain", "window") if not getattr(m, f).strip()}
    assert not holes, f"a registered metric with an empty field: {holes}"


def test_the_untested_metrics_only_become_fewer() -> None:
    reg = _registry()
    import gold_coverage as gc
    tests = gc.tests_naming(set(reg.REGISTRY))
    untested = sorted(reg.REGISTRY[o].name for o, t in tests.items() if not t)
    assert len(untested) <= _UNTESTED_CEILING, (
        f"{len(untested)} metrics named by no test (ceiling {_UNTESTED_CEILING}): {untested}")
