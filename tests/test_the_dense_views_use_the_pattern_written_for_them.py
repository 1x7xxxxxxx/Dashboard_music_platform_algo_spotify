"""`secondary_analyses()` was written for a note, and applied nowhere it was aimed.

R51. `src/dashboard/utils/ui.py` carries the function AND the reason for it — an
artist's 2026-08-12 remark, quoted in the file: too many charts on one screen. It was
used on four incidental views and on NONE of the five dense ones it was written for,
`trigger_algo` foremost (≈35 figures on one page).

This is `feedback_correct_code_nothing_reaches` in its purest form: code that is
correct, tested, documented — and applied nowhere it was meant to be. A render test
cannot see it, because every one of those charts renders perfectly.

The guard names the five views the brick names, and checks the pattern is present in
each. It asserts adoption, never a chart count: rebalancing a view is normal, and a
count would make ordinary work fail.
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
VIEWS = REPO / "src/dashboard/views"

# The five named in R51, with the figure counts measured when it was written.
_DENSE = {
    "trigger_algo": "≈35 figures (15 charts + up to 17 gauges)",
    "data_wrapped": "9 figures",
    "meta_creatives": "8 figures",
    "meta_ads_overview": "8 figures",
    "revenue_forecast": "6 figures",
}


def _files(view: str) -> list[pathlib.Path]:
    path = VIEWS / view
    return sorted(path.rglob("*.py")) if path.is_dir() else [VIEWS / f"{view}.py"]


def _calls_the_pattern(view: str) -> bool:
    """Is `secondary_analyses` actually CALLED here — read from the AST.

    Never a text search. The first version of this assertion searched the source, and
    the mutation that removed the real `with secondary_analyses(...)` left it green:
    the explanatory comment written beside the fix contains the name. A guard that
    passes on its own documentation guards the documentation.
    """
    import ast

    for f in _files(view):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name == "secondary_analyses":
                    return True
    return False


@pytest.mark.parametrize("view, density", sorted(_DENSE.items()))
def test_each_dense_view_collapses_its_secondary_charts(view, density):
    assert _calls_the_pattern(view), (
        f"{view} ({density}) shows everything at once. `secondary_analyses()` exists "
        "for exactly this and is one import away — nothing needs designing.")


def test_the_pattern_itself_is_still_there():
    """Non-vacuity: the parametrised assertions above all hinge on this name."""
    ui = (REPO / "src/dashboard/utils/ui.py").read_text(encoding="utf-8")
    assert "def secondary_analyses(" in ui
    assert "expanded=False" in ui, (
        "an expander opened by default collapses nothing — the point is the first "
        "screen")
