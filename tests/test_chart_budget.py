"""Guard — an artist-facing view opens on at most N decision charts.

Beta feedback (Grinch, 2026-08-12): "réduire le nombre de graphs qui permettent
de prendre décision". The charts were not wrong; too many of them competed for
the same decision, so none of them drove one. The rule adopted:

    a chart is PRIMARY if, alone, it can change what the artist does next;
    everything that only refines that answer goes inside `secondary_analyses()`,
    collapsed, one click away — deleted from the first screen, not from the code.

This test counts `st.plotly_chart` calls that are NOT nested in a
`secondary_analyses()` block, per view, and fails when a view exceeds its
budget. Adding a chart to a full view is then a deliberate act: either it earns
PRIMARY (raise the budget here, on purpose) or it goes in the expander.
"""
import ast
from pathlib import Path

import pytest

_VIEWS = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"

# Views an artist lands on to decide something, and their first-paint budget.
# Budgets are the CURRENT counts after the 2026-08-20 pass — they are a ratchet:
# lower them freely, raise one only with a reason written in the diff.
_BUDGET = {
    "instagram.py": 2,             # followers trend + engagement per month
    "soundcloud.py": 1,            # plays per track over time
    "youtube.py": 2,               # channel trend + top content
    "spotify_s4a_combined.py": 3,  # top songs + audience + per-song drill-down
    "apple_music.py": 2,
    "imusician.py": 2,
    "meta_x_spotify.py": 1,
}


def _primary_chart_count(path: Path) -> int:
    """st.plotly_chart calls not enclosed in a secondary_analyses() block."""
    tree = ast.parse(path.read_text(encoding="utf-8"))

    shielded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        if not any(
            isinstance(item.context_expr, ast.Call)
            and getattr(item.context_expr.func, "id", None) == "secondary_analyses"
            for item in node.items
        ):
            continue
        for inner in ast.walk(node):
            shielded.add(id(inner))

    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) == "plotly_chart"
        and id(node) not in shielded
    )


@pytest.mark.parametrize("filename,budget", sorted(_BUDGET.items()))
def test_view_opens_on_at_most_its_chart_budget(filename, budget):
    path = _VIEWS / filename
    assert path.exists(), f"{filename} listed in the budget but missing"
    count = _primary_chart_count(path)
    assert count <= budget, (
        f"{filename} paints {count} charts on open (budget {budget}). Either move "
        f"the refining ones into `with secondary_analyses(...)`, or raise the "
        f"budget here deliberately."
    )


def test_secondary_analyses_actually_shields_charts():
    """The counter must respond to the mechanism, or the budget means nothing."""
    src = (
        "import streamlit as st\n"
        "from src.dashboard.utils.ui import secondary_analyses\n"
        "st.plotly_chart(a)\n"
        "with secondary_analyses('x'):\n"
        "    st.plotly_chart(b)\n"
        "    st.plotly_chart(c)\n"
    )
    tmp = _VIEWS / "_chart_budget_probe.py"
    tmp.write_text(src, encoding="utf-8")
    try:
        assert _primary_chart_count(tmp) == 1
    finally:
        tmp.unlink()


def test_instagram_kept_its_charts_only_moved_them():
    """Reduction must be relocation, never deletion."""
    text = (_VIEWS / "instagram.py").read_text(encoding="utf-8")
    assert text.count("st.plotly_chart") == 4
    assert _primary_chart_count(_VIEWS / "instagram.py") == 2
