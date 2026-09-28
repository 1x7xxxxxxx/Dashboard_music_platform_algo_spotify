"""R243 — every chart of the app reaches the screen through ONE door, `charts.plotly_chart`.

Owner, 2026-09-27: « des légendes sur tous les graphes » (CPR was not defined anywhere he
looked), « toujours tracer en Pareto », « des couleurs qui permettent la distinction »
(fiche 39). A door only holds if nothing walks around it: a `.plotly_chart(` on any other
receiver in src/ is refused.
"""
import ast
import itertools
from pathlib import Path

import plotly.graph_objects as go

from src.dashboard.utils import charts
from src.dashboard.utils.colorimetry import de2000, lightness, simulate
from src.dashboard.utils.platform_colors import DISTINCT

ROOT = Path(__file__).resolve().parents[1]
DOOR = "src/dashboard/utils/charts.py"


def bypasses(tree: ast.AST) -> list[int]:
    """Lines where a chart is drawn by anything but the door. Pure."""
    # R314 — `pyplot` too: the three SHAP charts drew with `st.pyplot` and would have been
    # the only charts without the decision line the door writes under every figure.
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in ("plotly_chart", "pyplot")
            and not (isinstance(n.func.value, ast.Name) and n.func.value.id == "charts")]


def test_no_chart_walks_around_the_door():
    hits = [f"{f.relative_to(ROOT)}:{ln}" for f in (ROOT / "src").rglob("*.py")
            if f.relative_to(ROOT).as_posix() != DOOR
            for ln in bypasses(ast.parse(f.read_text(encoding="utf-8")))]
    assert not hits, f"draw through `charts.plotly_chart(fig, container=…)`: {hits}"


def test_the_detector_sees_the_defect_it_is_written_for():
    assert bypasses(ast.parse("st.plotly_chart(fig)"))
    assert bypasses(ast.parse("c1.plotly_chart(fig)"))
    assert bypasses(ast.parse("st.pyplot(plt.gcf())"))
    assert not bypasses(ast.parse("charts.pyplot(plt.gcf())"))
    assert not bypasses(ast.parse("charts.plotly_chart(fig, container=c1)"))
    assert not bypasses(ast.parse("'''st.plotly_chart(fig)'''"))


def test_the_jargon_is_defined_under_the_chart():
    fig = go.Figure([go.Bar(x=["a"], y=[1], name="CPR (€/clic)")])
    fig.update_layout(yaxis_title="CTR (%)")
    assert charts.jargon(fig) == ["CPR", "CTR"]
    assert charts.jargon(go.Figure([go.Bar(x=["a"], y=[1], name="Dépense")])) == []
    assert "CPRX" not in charts.GLOSSARY and charts.jargon(
        go.Figure([go.Bar(x=["a"], y=[1], name="SPRINT")])) == [], "a word containing PR"


def test_a_legend_appears_only_when_it_would_show_something():
    two = go.Figure([go.Scatter(y=[1], name="A"), go.Scatter(y=[2], name="B")])
    assert charts.apply_defaults(two).layout.showlegend is True
    hidden = go.Figure([go.Bar(y=[1], name="A", showlegend=False),
                        go.Bar(y=[2], name="B", showlegend=False)])
    assert charts.apply_defaults(hidden).layout.showlegend is None, "an empty legend band"
    own = go.Figure([go.Scatter(y=[1], name="A"), go.Scatter(y=[2], name="B")])
    own.update_layout(legend=dict(orientation="v"))
    assert charts.apply_defaults(own).layout.legend.orientation == "v", "overrode a chosen legend"


def test_pareto_is_opt_in_and_puts_the_biggest_first():
    fig = go.Figure([go.Bar(x=["a", "b"], y=[1, 3])])
    assert charts.apply_defaults(fig).layout.xaxis.categoryorder is None, "Pareto must be opt-in"
    assert charts.apply_defaults(fig, pareto=True).layout.xaxis.categoryorder == "total descending"
    h = go.Figure([go.Bar(y=["a", "b"], x=[1, 3], orientation="h")])
    assert charts.apply_defaults(h, pareto=True).layout.yaxis.categoryorder == "total ascending"


def test_the_default_palette_is_told_apart_in_every_vision():
    worst = min(min(de2000(a, b), de2000(simulate(a, "deutan"), simulate(b, "deutan")),
                    de2000(simulate(a, "protan"), simulate(b, "protan")))
                for a, b in itertools.combinations(DISTINCT, 2))
    assert worst >= 15.0, f"worst pair ΔE {worst:.1f} under the floor of 15"
    assert all(0.43 <= lightness(c) <= 0.77 for c in DISTINCT)


def test_the_door_survives_every_trace_type():
    """R243 regression, found by the R245 render: the door read `marker.color`, a Pie has
    `marker.colors` and an Indicator no marker — every page with a ring crashed in prod."""
    traces = [go.Pie(values=[1, 2], marker=dict(colors=["red", "blue"])), go.Pie(values=[1]),
              go.Indicator(value=3), go.Funnel(x=[3, 2]), go.Heatmap(z=[[1]]),
              go.Scatterpolar(r=[1]), go.Histogram(x=[1]), go.Box(y=[1]),
              go.Waterfall(y=[1]), go.Treemap(labels=["a"], parents=[""]), go.Choropleth()]
    for tr in traces:
        fig = go.Figure([tr])
        charts.apply_defaults(fig, pareto=True)
        charts.jargon(fig)
    coloured = go.Figure([go.Pie(values=[1], marker=dict(colors=["#123456"]))])
    assert not charts.apply_defaults(coloured).layout.colorway, "a Pie's own colours were overridden"
