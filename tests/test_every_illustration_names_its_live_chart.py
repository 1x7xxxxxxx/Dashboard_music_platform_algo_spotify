"""Guard (R551): every example illustration names where it is drawn for real.

Type: Utility
Uses: ast, src.dashboard.utils.example_figures
Triggers: pytest
Persists in: nothing

The assistant (`onboarding`) and the overview (`algo_preview`) show offline PNG
illustrations. The owner asked on 2026-10-13 whether they are « bien présents dans la vue
croisée ». They are not, and `ILLUSTRATION_COUNTERPART` records the measured answer: per
illustration, the live functions that draw its content, and what the Vue croisée misses.

This guard keeps that record true:
- a new illustration shown by a page must enter the map;
- every named live function must still exist in its file (a rename or a move makes the
  record lie, the `/kpis` → `/youtube` drift shape);
- a « partial » claim must name a counterpart on the Vue croisée itself.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src.dashboard.utils import example_figures as ef

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHOWN = {ef.OVERVIEW, *ef.PROMISES, *ef.ALGO_PREVIEW}
MAP = ef.ILLUSTRATION_COUNTERPART


def _functions(path: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_every_shown_illustration_is_mapped():
    assert SHOWN - MAP.keys() == set(), f"illustrations sans correspondance : {SHOWN - MAP.keys()}"


def test_every_illustration_file_exists():
    missing = [n for n in MAP if not (ef.EXAMPLES_DIR / n).exists()]
    assert not missing, f"illustrations référencées mais absentes : {missing}"


@pytest.mark.parametrize("name", sorted(MAP))
def test_every_counterpart_function_exists(name):
    for _page, path, func in MAP[name]["counterparts"]:
        assert (ROOT / path).exists(), f"{name} : {path} n'existe plus"
        assert func in _functions(path), f"{name} : {func} n'est plus dans {path}"


@pytest.mark.parametrize("name", sorted(MAP))
def test_the_cross_view_claim_matches_the_counterparts(name):
    entry = MAP[name]
    assert entry["cross_view"] in {"partial", "absent"}, entry["cross_view"]
    assert entry["gap"].strip(), f"{name} : l'écart n'est pas dit"
    on_cross = [c for c in entry["counterparts"] if c[0] == "meta_ads_overview"]
    if entry["cross_view"] == "partial":
        assert on_cross, f"{name} : « partial » sans figure de la vue croisée"
    else:
        assert not on_cross, f"{name} : « absent » mais une figure de la vue croisée est nommée"
