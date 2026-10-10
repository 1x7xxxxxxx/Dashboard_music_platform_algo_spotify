"""R512 (X1, 2026-10-11) — the home tiles are two rows of two, the pairs kept together.

Type: Guard
Uses: src/dashboard/views/home_tiles.py (ast)
Depends on: nothing at runtime
Persists in: nothing

Owner : « sur la même ligne Meta Ads, Hypeddit, et sur la même ligne Shazam et Instagram ».
R423 had put the four on one row of four columns.

Mutation record (2026-10-11): seen red with `par_rangee=4` and with `st.columns(4)`.
"""
from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src/dashboard/views/home_tiles.py"


def _calls(name: str) -> list[ast.Call]:
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", getattr(n.func, "id", None)) == name]


def test_the_tiles_are_laid_out_two_per_row() -> None:
    lay = [c for c in _calls("agencer") if c.args and getattr(c.args[0], "id", "") == "_unites"]
    assert lay, "anti-vacuity: agencer(_unites, …) not found"
    rows = {kw.value.value for c in lay for kw in c.keywords if kw.arg == "par_rangee"}
    assert rows == {2}, f"tiles per row: {rows}"


def test_each_row_has_two_columns() -> None:
    from src.dashboard.views.home_tiles import agencer
    pairs = [[("m", 0), ("h", 0)], [("s", 0), ("i", 0)]]
    assert [len(r) for r in agencer(pairs, par_rangee=2)] == [2, 2]
    widths = {c.args[0].value for c in _calls("columns")
              if c.args and isinstance(c.args[0], ast.Constant) and c.args[0].value in (2, 4)}
    assert 4 not in widths, "a four-column row survives in the home tiles"
