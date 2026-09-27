"""R258 — a cost or rate ratio (CPC, CPM, CPR, CTR) is computed by ONE function.

Type: Test
Uses: src/dashboard/utils/ratios.py, src/dashboard/views/**/*.py (parsed with ast)

Critic verdict (critic-2026-09-27.md, R258 d) : one pure shared ratio function. Measured
2026-09-27 : the CPC three ways in three files, and `_campaign_frame` wrote 0 for a
campaign without results/clicks/impressions — a bar at « 0 € », the cheapest campaign of
the account on screen. Seven inline sites moved to `ratios.per` / `per_series`.

The scan reads the SYNTAX TREE: a division whose left side names a spend and whose right
side names clicks, impressions, conversions or results. SQL strings are not Python
divisions and are not counted (they are aggregated in the base, which is the gold path).

Mutation record (2026-09-28) : `per` answering 0 on a zero denominator → red ; one
inline `spend / clicks` put back in a view → red.
"""
import ast
import math
from pathlib import Path

import pandas as pd

from src.dashboard.utils.ratios import per, per_series

VIEWS = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"
_SPEND = ("spend", "depense", "dépense", "cost")
_BASES = ("click", "clic", "impression", "conversion", "result")


def _names(node: ast.AST) -> str:
    return " ".join(
        [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]
        + [n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)]
        + [n.value for n in ast.walk(node) if isinstance(n, ast.Constant)
           and isinstance(n.value, str)]).lower()


def inline_ratios(root: Path = VIEWS) -> list[str]:
    hits = []
    for p in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                left, right = _names(node.left), _names(node.right)
                if any(s in left for s in _SPEND) and any(b in right for b in _BASES):
                    hits.append(f"{p.name}:{node.lineno}")
    return hits


def test_an_undefined_ratio_is_absent_never_zero():
    assert per(10, 4) == 2.5 and per(1, 4, 1000) == 250.0
    for den in (0, None, float("nan"), -3):
        assert per(10, den) is None
    s = per_series(pd.Series([10.0, 5.0]), pd.Series([2, 0]))
    assert s.iloc[0] == 5.0 and math.isnan(s.iloc[1])


def test_no_view_divides_a_spend_by_hand():
    assert not inline_ratios(), f"ratios faits main — utiliser utils.ratios : {inline_ratios()}"


def test_the_scan_is_not_vacuous(tmp_path):
    (tmp_path / "v.py").write_text(
        "# spend / clicks in a comment\n"
        "q = 'SELECT spend / clicks FROM t'\n"
        "a = d['spend'] / d['clicks']\n"
        "b = x.total_spend / x.total_impressions * 1000\n", encoding="utf-8")
    assert inline_ratios(tmp_path) == ["v.py:3", "v.py:4"]
