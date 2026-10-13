"""R557 — one tool ranks every setting an artist can change, the one to keep in green.

Owner Y2 of 2026-10-13, fiches 36, 38, 41, 53: the spend × CPR cloud, the creative ×
week heatmap and the algo page's settings bars are gone; « 🧪 Tes meilleurs réglages »
answers « qu'est-ce que je change ? » once, for the creative, hook, country, placement,
platform, age, button and objective.
"""
import ast
from pathlib import Path

import pandas as pd

from src.dashboard.utils import best_settings
from src.dashboard.utils.semantic_colors import BON

ROOT = Path(__file__).resolve().parent.parent


def _frame(rows):
    return pd.DataFrame(rows, columns=["v", "spend", "results"])


def test_a_value_is_summed_across_its_rows():
    r = best_settings.rank(_frame([("A", 30, 30), ("A", 30, 30), ("B", 70, 20)]), "v")
    a = r.set_index("valeur").loc["A"]
    assert (a["depense"], a["resultats"], round(a["cpr"], 3)) == (60, 60, 1.0)


def test_a_thin_value_is_never_the_best():
    # C is the cheapest but only 5 results: grey, never green.
    r = best_settings.rank(_frame([("A", 100, 50), ("B", 100, 25), ("C", 100, 5)]), "v")
    assert not r.set_index("valeur").loc["C", "fiable"]
    b = best_settings.best(r)
    assert b["valeur"] == "A" and b["eviter"] == "B"


def test_a_verdict_needs_two_reliable_values():
    r = best_settings.rank(_frame([("A", 100, 50), ("C", 100, 5)]), "v")
    assert best_settings.best(r) is None
    assert best_settings.verdicts([("x", r)]) == []


def test_the_figure_greens_the_best_only():
    r = best_settings.rank(_frame([("A", 100, 50), ("B", 100, 25), ("C", 100, 5)]), "v")
    bar = best_settings.figure([("Créative", r)]).data[0]
    colours = dict(zip([y.replace(" ⚠️", "") for y in bar.y], bar.marker.color))
    assert colours["A"] == BON and colours["B"] != BON and colours["C"] != BON
    assert best_settings.figure([("x", r.iloc[0:0])]) is None


def _defs(rel: str) -> set[str]:
    """Top-level function and variable names of a module."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    return names | {t.id for n in tree.body if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)}


def test_the_three_old_answers_are_gone_and_the_tool_is_wired():
    cr = _defs("src/dashboard/views/meta_creatives.py")
    assert {"_render_best_settings", "_render_spend_pareto", "_Q_AXE"} <= cr
    assert not {"_render_scatter", "_render_activity", "_render_funnel"} & cr
    assert not {"_Q_AXE", "_rendre_axe", "_figure_axe"} & _defs(
        "src/dashboard/views/trigger_algo/_tab_reglages.py")


def test_the_body_calls_the_tool():
    tree = ast.parse((ROOT / "src/dashboard/views/meta_creatives.py").read_text("utf-8"))
    body = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "_render_body")
    calls = {ast.unparse(c.func) for c in ast.walk(body) if isinstance(c, ast.Call)}
    assert {"_render_best_settings", "_render_spend_pareto"} <= calls, calls
