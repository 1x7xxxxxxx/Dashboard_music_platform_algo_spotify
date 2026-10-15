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
    assert "_render_spend_pareto" in cr
    assert not {"_render_scatter", "_render_activity", "_render_funnel"} & cr
    # R598 (owner, 2026-10-15) moved the tool to the algo page: it is read there only.
    assert not {"_render_best_settings", "_settings_panels", "_Q_AXE"} & cr
    assert "_Q_AXE" in _defs("src/dashboard/views/trigger_algo/_settings_data.py")
    # R570 (2026-10-15) deleted `trigger_algo/_tab_reglages.py`, the third old answer.
    assert not (ROOT / "src/dashboard/views/trigger_algo/_tab_reglages.py").exists()


def test_the_body_calls_the_tool():
    tree = ast.parse((ROOT / "src/dashboard/views/meta_creatives.py").read_text("utf-8"))
    body = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "_render_body")
    calls = {ast.unparse(c.func) for c in ast.walk(body) if isinstance(c, ast.Call)}
    assert "_render_spend_pareto" in calls and "_render_best_settings" not in calls, calls


def test_each_panel_puts_the_value_to_keep_on_top():
    """R568 — Pareto, best on top, AFTER the chart door: its own Pareto sort (« total
    ascending ») lifted a cheap ⚠️ value above the green one."""
    from src.dashboard.utils import charts
    # C is the cheapest (5 results, unreliable), A the best reliable value, B dearer.
    r = best_settings.rank(_frame([("B", 100, 25), ("C", 100, 5), ("A", 100, 50)]), "v")
    r.loc[r["valeur"] == "C", "cpr"] = 0.5   # cheapest of the three, still grey
    fig = charts.apply_defaults(best_settings.figure([("x", r), ("y", r)]))
    for axis in (fig.layout.yaxis, fig.layout.yaxis2):
        assert axis.autorange == "reversed"
        assert list(axis.categoryarray)[0] == "A", list(axis.categoryarray or [])
        assert axis.categoryorder == "array"


def test_the_colours_are_the_campaigns_named_in_the_legend():
    """R597 (owner, 2026-10-15) — « les couleurs = les campagnes, avec leur légende »: one
    trace per campaign in every panel, its colour the campaign's, in the legend once."""
    f = pd.DataFrame([("A", 100, 50, "C1"), ("B", 100, 25, "C1"),
                      ("A", 100, 20, "C2"), ("B", 100, 40, "C2")],
                     columns=["v", "spend", "results", "camp"])
    r = best_settings.rank_by(f, "v", "camp")
    colours = {"C1": "#0000ff", "C2": "#ffcc00"}
    fig = best_settings.figure([("x", r), ("y", r)], colours=colours)
    assert [(tr.name, tr.marker.color) for tr in fig.data] == [
        ("C1", "#0000ff"), ("C2", "#ffcc00")] * 2
    assert [tr.showlegend for tr in fig.data] == [True, True, False, False]
    assert fig.layout.showlegend is True
    # Each campaign's own best wears the ★: A for C1, B for C2.
    stars = {tr.name: [y for y, txt in zip(tr.y, tr.text) if "★" in txt] for tr in fig.data}
    assert stars == {"C1": ["A"], "C2": ["B"]}
