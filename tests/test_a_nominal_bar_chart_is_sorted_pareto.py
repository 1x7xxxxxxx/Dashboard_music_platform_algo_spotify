"""R260 — bars over nominal categories are sorted by total (Pareto) by default; an order
that carries a meaning is never touched.

Type: Test
Uses: src/dashboard/utils/charts.py (apply_defaults, pareto_by_default, nominal_categories)

Owner, 2026-09-27 (fiches 28, 29, 33) : « toujours tracer en Pareto, filtrer en Pareto tous
nos graphiques ». Before R260 Pareto was opt-in and three charts asked for it.
"""
import plotly.graph_objects as go

from src.dashboard.utils import charts


def _bar(x, **kw):
    return go.Figure(go.Bar(x=x, y=list(range(len(x), 0, -1)), **kw))


def test_nominal_categories_are_sorted_by_total():
    fig = charts.apply_defaults(_bar(["France", "Brésil", "Canada", "Japon"]))
    assert fig.layout.xaxis.categoryorder == "total descending"
    h = go.Figure(go.Bar(y=["créa A", "créa B", "créa C"], x=[1, 3, 2], orientation="h"))
    assert charts.apply_defaults(h).layout.yaxis.categoryorder == "total ascending"


def test_an_order_with_a_meaning_is_never_reordered():
    for cats in (["18-24", "25-34", "35-44"], ["7 jours", "28 jours", "12 mois"],
                 ["2026-07", "2026-08", "2026-09"], ["janv.", "févr.", "mars"],
                 ["Lun", "Mar", "Mer"]):
        assert not charts.pareto_by_default(_bar(cats)), cats
    funnel = _bar(["Impressions", "Clics", "Écoutes"], name="Entonnoir")
    assert not charts.pareto_by_default(funnel)
    chosen = _bar(["b", "a", "c"])
    chosen.update_xaxes(categoryorder="array", categoryarray=["b", "a", "c"])
    assert not charts.pareto_by_default(chosen)
    mixed = _bar(["a", "b", "c"])
    mixed.add_trace(go.Scatter(x=["a", "b", "c"], y=[1, 2, 3]))
    assert not charts.pareto_by_default(mixed), "a line over the bars reads their order"


def test_an_explicit_choice_wins():
    fig = charts.apply_defaults(_bar(["France", "Brésil", "Canada"]), pareto=False)
    assert fig.layout.xaxis.categoryorder in (None, "trace")


def test_the_detector_needs_three_labels():
    assert not charts.nominal_categories(["A", "B"])
    assert charts.nominal_categories(["Instagram", "Facebook", "Audience Network"])
