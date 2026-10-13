"""R561 — the Trésorerie in green and red, one circle beside it, the point mort and the ROI
regression in ONE figure, the trigger chart said in words.

Type: Guard
Uses: src.dashboard.utils.treasury_chart (cashflow_figure, breakeven_figure),
      src/dashboard/views/revenue_forecast.py (AST, trigger_paragraph)
Depends on: nothing
Persists in: nothing

Owner, Trésorerie notes of 2026-10-13 (evening) : « un dégradé de couleur verte pour les
entrées et un dégradé de couleur rouge pour les sorties » ; « un cercle aligné avec le
graphique l'argent mois par mois […] que le total fasse 100 % » ; « fusionner le graphique
point mort et le graphique ROI régression linéaire en un seul » ; and of the trigger chart,
« je ne comprends pas la valeur ajoutée de ce graphique ».
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from src.dashboard.utils.treasury_chart import breakeven_figure, cashflow_figure

_VIEW = Path("src/dashboard/views/revenue_forecast.py")


def _cashflow() -> pd.DataFrame:
    rows = [("revenu", "imusician", 30.0, 1), ("revenu", "sacem", 5.0, 1),
            ("depense", "meta_ads", 50.0, -1), ("depense", "distribution", 15.0, -1)]
    return pd.DataFrame([{"year": 2025, "month": m, "flux": f, "source": s,
                          "amount_eur": v, "direction": d}
                         for m in (1, 2, 3) for f, s, v, d in rows])


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def test_money_in_is_green_money_out_is_red_biggest_darkest() -> None:
    fig = cashflow_figure(_cashflow())
    bars = {tr.name: _rgb(tr.marker.color) for tr in fig.data if tr.type == "bar"}
    for name in ("iMusician", "SACEM"):
        r, g, b = bars[name]
        assert g > r and g > b, f"{name} (money in) is not a green: {bars[name]}"
    for name in ("Publicité Meta", "Distribution"):
        r, g, b = bars[name]
        assert r > g and r > b, f"{name} (money out) is not a red: {bars[name]}"
    assert sum(bars["iMusician"]) < sum(bars["SACEM"]), "the biggest inflow is not the darkest"
    assert sum(bars["Publicité Meta"]) < sum(bars["Distribution"]), (
        "the biggest outflow is not the darkest")


def test_one_circle_beside_the_bars_sums_to_100_in_the_same_colours() -> None:
    fig = cashflow_figure(_cashflow())
    (pie,) = [tr for tr in fig.data if tr.type == "pie"]
    assert abs(sum(pie.values) - 100.0) < 1e-9, "the circle is not the whole of the money"
    bars = {tr.name: tr.marker.color for tr in fig.data if tr.type == "bar"}
    assert dict(zip(pie.labels, pie.marker.colors)) == bars, "the circle's shades are not the bars'"
    assert list(pie.labels)[:2] == ["iMusician", "SACEM"], "money in does not open the circle"
    assert pie.values[0] == 100 * 90 / 300, pie.values


def _break_even() -> object:
    cf = _cashflow()
    months = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=3, freq="MS")})
    return breakeven_figure(cf, months, projection_months=6)


def test_the_point_mort_is_the_diagonal_of_a_spend_by_revenue_plane() -> None:
    fig = _break_even()
    assert fig.layout.xaxis.type == "log" and fig.layout.yaxis.type == "log"
    (diag,) = [tr for tr in fig.data if tr.line.dash == "dash"]
    assert list(diag.x) == list(diag.y), "the break-even is not the line revenue = spend"
    (path,) = [tr for tr in fig.data if tr.mode == "lines+markers+text"]
    assert list(path.x) == [65.0, 130.0, 195.0], "x is not the spend cumulated"
    assert list(path.y) == [35.0, 70.0, 105.0], "y is not the revenue cumulated"


def test_the_revenue_trend_continues_the_path_dotted() -> None:
    fig = _break_even()
    (proj,) = [tr for tr in fig.data if tr.line.dash == "dot"]
    assert (proj.x[0], proj.y[0]) == (195.0, 105.0), "the trend does not start on today"
    assert proj.y[-1] == 105.0 + 6 * 35.0 and proj.x[-1] == 195.0 + 6 * 65.0


def _functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def test_the_trigger_and_the_fit_are_words_not_charts() -> None:
    fns = _functions()
    assert "_render_trigger_value" not in fns and "_render_fit" not in fns
    for name in ("_render_trigger_sentence", "render_spend_revenue_fit", "render_artist_money"):
        calls = {getattr(c.func, "attr", getattr(c.func, "id", ""))
                 for c in ast.walk(fns[name]) if isinstance(c, ast.Call)}
        assert not calls & {"plotly_chart", "Figure"}, f"{name} draws a chart again"


def test_the_trigger_paragraph_says_what_each_number_is_made_of() -> None:
    from src.dashboard.views.revenue_forecast import trigger_paragraph
    row = {"streams_med": 6000.0, "valeur_eur": 23.78, "n": 104}
    espoir = {"par_algo": pd.DataFrame([{"algo": "DW", "proba_moyenne": 0.068,
                                         "esperance_eur": 17.99, "titres": 11}])}
    text = trigger_paragraph(row, 0.003963, espoir)
    for part in ("6 000 écoutes", "0,0040 € l'écoute", "23,78 €", "11 titres", "6,8 %", "17,99 €"):
        assert part.replace(" ", " ") in text.replace(" ", " "), (part, text)
