"""No view prices a playlist threshold as streams to buy (R402).

Type: Guard
Uses: src/ (AST), src.utils.ml_outcome_labeling, src.dashboard.views.trigger_algo._common
Depends on: nothing
Persists in: nothing

Found by the critic of R380/R381 (2026-10-05): the Budget & ROI tab multiplied
417/1333/8423 by the cost per stream and printed « ✅ Budget suffisant » under a caption
naming a SHAP source that does not exist. Those numbers are the volume a playlist
PRODUCES once installed — the PDF says so: « pas un objectif de streams à atteindre
soi-même ». A third set, 9200/4100…, had no source at all.

Two properties are held:
  1. a threshold set lives in ONE place — `TARGET_THRESHOLDS`; no other module binds a
     literal carrying those values or the steady-state ones;
  2. no argument of `budget_pour_streams` (the one euro formula, R372) is read from a
     threshold-like name — the only honest quantity to price is a GAP.
"""
from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path("src")
_HOME = Path("src/utils/ml_outcome_labeling.py")
# Each set, as it would be written: the entry thresholds, the steady-state volumes,
# and the unsourced 28-day gate.
_SETS = {
    "entry thresholds": {130, 137, 639},
    "steady-state volumes": {417, 1333, 8423},
    "unsourced 28-day gate": {9200, 4100, 1300, 8400},
}
_THRESHOLD_WORDS = ("THRESHOLD", "TARGET", "SEUIL", "ELBOW", "STEADY", "GATE")


def _modules():
    for path in sorted(_SRC.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def _int_literals(node: ast.AST) -> set[int]:
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and type(n.value) is int}


def test_each_threshold_set_is_bound_once() -> None:
    sites = []
    for path, tree in _modules():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Dict, ast.Set, ast.List, ast.Tuple)):
                continue
            found = _int_literals(node)
            for name, values in _SETS.items():
                if len(found & values) >= 3 and not (path == _HOME and name == "entry thresholds"):
                    sites.append(f"{path}:{node.lineno} ({name})")
    assert not sites, (
        "a threshold set is written outside `ml_outcome_labeling.TARGET_THRESHOLDS` — "
        f"read it from there, or delete it if it is not a threshold: {sorted(set(sites))}")


def _names(node: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _loop_sources(tree: ast.AST) -> dict[str, set[str]]:
    """Loop variable → the names its iterable reads (`for label, seuil in X.items()`)."""
    src: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.comprehension)):
            for target in _names(node.target):
                src.setdefault(target, set()).update(_names(node.iter))
    return src


def test_no_budget_is_computed_from_a_threshold() -> None:
    sites = []
    for path, tree in _modules():
        loops = _loop_sources(tree)
        for call in ast.walk(tree):
            if not (isinstance(call, ast.Call)
                    and getattr(call.func, "id", getattr(call.func, "attr", "")) == "budget_pour_streams"):
                continue
            read = set()
            for arg in call.args + [k.value for k in call.keywords]:
                for name in _names(arg):
                    read |= {name} | loops.get(name, set())
            hits = sorted(n for n in read if any(w in n.upper() for w in _THRESHOLD_WORDS))
            if hits:
                sites.append(f"{path}:{call.lineno} reads {hits}")
    assert not sites, (
        "a budget is priced from a threshold — a threshold is not a number of streams to "
        f"buy; price the GAP instead: {sites}")


def test_the_view_reads_the_labeling_thresholds() -> None:
    from src.dashboard.views.trigger_algo._common import ELBOW_THRESHOLDS_28D
    from src.utils.ml_outcome_labeling import TARGET_THRESHOLDS

    assert ELBOW_THRESHOLDS_28D == {k.upper(): v for k, v in TARGET_THRESHOLDS.items()}
