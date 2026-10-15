"""R565/R574 — the door puts a legend ON the plot where it hides the fewest points, never below.

Type: Test
Uses: src.dashboard.utils.charts (apply_defaults, legend_position), utils.legend_place
Depends on: nothing
Persists in: nothing

Owner, 2026-10-15: « les légendes sont mal placées partout ». R536's fixed top-right
corner sat on every rising line and on every Pareto's tallest bar.
"""
from __future__ import annotations

import plotly.graph_objects as go

from src.dashboard.utils import charts
from src.dashboard.utils.legend_place import least_covered, paper_points


def _corner(fig) -> tuple:
    leg = charts.apply_defaults(fig).layout.legend
    return leg.yanchor, leg.xanchor, leg.yref


def test_a_rising_line_moves_the_legend_off_the_top_right() -> None:
    fig = go.Figure([go.Scatter(y=[1, 5, 10], name="a"), go.Scatter(y=[0, 4, 9], name="b")])
    assert _corner(fig)[:2] == ("top", "left")


def test_a_falling_line_keeps_the_top_right() -> None:
    fig = go.Figure([go.Scatter(y=[10, 5, 1], name="a"), go.Scatter(y=[9, 4, 0], name="b")])
    assert _corner(fig)[:2] == ("top", "right")


def test_a_pareto_is_read_in_its_drawn_order() -> None:
    # unsorted data, the door sorts the tallest bar to the LEFT: top right is free
    # (as given, the tallest bar would stand in the top right corner)
    fig = go.Figure([go.Bar(x=["c", "b", "a"], y=[1, 5, 9], name="n"),
                     go.Bar(x=["c", "b", "a"], y=[1, 4, 8], name="m")])
    assert charts.pareto_by_default(fig)
    assert _corner(fig)[:2] == ("top", "right")


def test_stacked_bars_are_as_tall_as_their_sum() -> None:
    fig = go.Figure([go.Bar(x=["a", "b", "c"], y=[5, 5, 5], name="p"),
                     go.Bar(x=["a", "b", "c"], y=[5, 0, 0], name="q")])
    fig.update_layout(barmode="stack")
    top_of_c = max(y for x, y in paper_points(fig) if x > 0.9)
    assert top_of_c == 0.5  # 5 of a 10-high stack; side by side it would read 5 of 5


def test_a_full_plot_keeps_the_legend_on_the_plot_where_it_hides_least() -> None:
    # R574 (owner, 2026-10-15): « sur le graphique, à l'endroit le moins gênant », never below
    fig = go.Figure([go.Scatter(x=[0, 1, 0, 1], y=[0, 0, 1, 1], name="a", mode="markers"),
                     go.Scatter(x=[0, 1], y=[1, 0], name="b")])
    out = charts.apply_defaults(fig)
    assert out.layout.legend.yref != "container" and out.layout.legend.y >= 0
    assert out.layout.margin.b is None
    # the X crosses every corner; the middle of the top edge is the emptiest place
    assert least_covered(fig, 2) == ("top center", 0)


def test_the_least_covered_place_wins_over_the_first_corner() -> None:
    # dense along the top, a single stray point bottom right: bottom left is best
    xs = [i / 20 for i in range(21)]
    fig = go.Figure([go.Scatter(x=xs, y=[1] * 21, name="a", mode="markers"),
                     go.Scatter(x=[1, 0.5], y=[0, 0], name="b", mode="markers")])
    place, n = least_covered(fig, 2)
    assert place == "bottom left" and n == 0


def test_a_hidden_trace_does_not_block_a_corner() -> None:
    fig = go.Figure([go.Scatter(y=[10, 5, 1], name="a"),
                     go.Scatter(y=[0, 5, 10], name="b", visible="legendonly")])
    assert least_covered(fig, 2) == ("top right", 0)


def test_a_log_axis_is_read_in_its_own_scale() -> None:
    # linear reading puts 10 and 100 both near the bottom; log spreads them evenly
    fig = go.Figure([go.Scatter(x=[0, 1, 2], y=[1, 10, 1000], name="a", mode="markers")])
    fig.update_yaxes(type="log")
    mid = sorted(y for _, y in paper_points(fig))[1]
    assert abs(mid - 1 / 3) < 0.01


def _legends():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "tools/dev/charts_dossier/legends.py"
    spec = importlib.util.spec_from_file_location("legends_inventory", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_inventory_reads_the_place_the_door_chose() -> None:
    legends = _legends()
    up = charts.apply_defaults(go.Figure([go.Scatter(y=[1, 5, 10], name="a"),
                                          go.Scatter(y=[0, 4, 9], name="b")]))
    assert legends.legend_of(up.to_plotly_json()) == {"entries": ["a", "b"],
                                                      "place": "haut gauche", "covered": 0}
    full = charts.apply_defaults(go.Figure([
        go.Scatter(x=[0, 1, 0, 1], y=[0, 0, 1, 1], name="a", mode="markers"),
        go.Scatter(x=[0, 1], y=[1, 0], name="b")]))
    assert legends.legend_of(full.to_plotly_json())["place"] == "haut centre"
    alone = go.Figure([go.Scatter(y=[1, 2], name="a")])
    assert legends.legend_of(alone.to_plotly_json()) == {"entries": [], "place": "—",
                                                         "covered": 0}


def test_a_bar_over_dates_keeps_its_dates_spread() -> None:
    # Trésorerie, 2026-10-15 capture: the bars' zero was added to the DATE axis too —
    # every month landed on the right edge and the legend sat on the balance line
    fig = go.Figure([go.Bar(x=["2024-01-01", "2024-06-01"], y=[-5, -1], name="a"),
                     go.Scatter(x=["2024-01-01", "2024-06-01"], y=[0, -6], name="b")])
    xs = {round(x, 2) for x, _ in paper_points(fig)}
    assert min(xs) == 0.0 and max(xs) == 1.0


def test_relative_bars_stack_negatives_downward() -> None:
    fig = go.Figure([go.Bar(x=["a", "b"], y=[-4, -4], name="p"),
                     go.Bar(x=["a", "b"], y=[4, 0], name="q"),
                     go.Scatter(x=["b"], y=[4], name="m", mode="markers")])
    fig.update_layout(barmode="relative")
    top_of_a = max(y for x, y in paper_points(fig) if x < 0.5)
    assert top_of_a == 1.0  # +4 rises from zero, not from the -4 below it


def test_a_date_range_given_as_dates_is_read_as_dates() -> None:
    # cross view « chrono », 2026-10-15: a range of Timestamps on an untyped axis crashed
    # the page (float − Timestamp); the range must also be HONOURED, not dropped
    import pandas as pd
    fig = go.Figure([go.Scatter(x=["2024-01-01", "2024-01-11"], y=[0, 1], name="a"),
                     go.Scatter(x=["2024-01-01", "2024-01-11"], y=[1, 0], name="b")])
    fig.update_xaxes(range=[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-21")])
    xs = [x for x, _ in paper_points(fig)]
    assert abs(max(xs) - 0.5) < 0.01  # 10 of the 20 days shown
