"""R561 — the Trésorerie in green and red, one circle beside it, the point mort and the ROI
regression in ONE figure, the trigger chart said in words.

Type: Guard
Uses: src.dashboard.utils.treasury_chart (cashflow_figure, breakeven_figure),
      src/dashboard/views/revenue_forecast.py (AST, render_artist_money)
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


def test_the_circle_says_each_source_in_euros_in_the_bars_colours() -> None:
    # R566 (owner, 2026-10-15 : « le montant en euros et le nom, pas de pourcentage »)
    fig = cashflow_figure(_cashflow())
    (pie,) = [tr for tr in fig.data if tr.type == "pie"]
    bars = {tr.name: tr.marker.color for tr in fig.data if tr.type == "bar"}
    assert dict(zip(pie.labels, pie.marker.colors)) == bars, "the circle's shades are not the bars'"
    assert list(pie.labels)[:2] == ["iMusician", "SACEM"], "money in does not open the circle"
    assert dict(zip(pie.labels, pie.values)) == {
        "iMusician": 90.0, "SACEM": 15.0, "Publicité Meta": 150.0, "Distribution": 45.0}
    assert "€" in pie.texttemplate and "percent" not in (pie.texttemplate + (pie.textinfo or ""))
    assert "%" not in pie.title.text and "105" in pie.title.text, pie.title.text


def test_the_title_says_revenue_green_spend_red_and_roi_by_its_sign() -> None:
    from src.dashboard.utils.treasury_chart import (
        BREAKEVEN_REVENUE as GREEN, BREAKEVEN_SPEND as RED, breakeven_title)
    loss = breakeven_title(105.0, 195.0)
    assert f"color:{GREEN}'>105 €" in loss and f"color:{RED}'>195 €" in loss, loss
    assert f"color:{RED}'>-46 %" in loss, loss
    gain = breakeven_title(300.0, 200.0)
    assert f"color:{GREEN}'>+50 %" in gain, gain


def test_the_projection_is_marked_at_2_10_30_and_50_years() -> None:
    from src.dashboard.utils.treasury_chart import (
        PROJECTION_CAP_MONTHS, breakeven_text, projection_marks)
    assert PROJECTION_CAP_MONTHS == 600
    marks = projection_marks(PROJECTION_CAP_MONTHS)
    assert {i: m for i, m in enumerate(marks) if m} == {
        24: "2 ans", 120: "10 ans", 360: "30 ans", 600: "50 ans"}
    far = breakeven_text({"etat": "atteint", "mois": 900, "cumul": -500.0, "rythme": 0.5,
                          "date": None})
    assert "pas avant <b>50 ans</b>" in far and "plus de" not in far, far
    mid = breakeven_text({"etat": "atteint", "mois": 120, "cumul": -500.0, "rythme": 4.0,
                          "date": pd.Timestamp("2036-10-01")})
    assert "≈ 10 ans" in mid and "10/2036" in mid, mid


def _break_even() -> object:
    cf = _cashflow()
    months = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=3, freq="MS")})
    return breakeven_figure(cf, months, projection_months=6)


def test_the_point_mort_is_the_diagonal_of_a_spend_by_revenue_plane() -> None:
    fig = _break_even()
    assert fig.layout.xaxis.type == "log" and fig.layout.yaxis.type == "log"
    (diag,) = [tr for tr in fig.data if tr.line.dash == "dash"]
    assert list(diag.x) == list(diag.y), "the break-even is not the line revenue = spend"
    (path,) = [tr for tr in fig.data if tr.name == "Toi, mois après mois"]
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


def _i18n_keys_called(path: Path) -> set[str]:
    """The keys a module passes to `t(...)` — its code, never its comments."""
    return {c.args[0].value for c in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "t" and c.args
            and isinstance(c.args[0], ast.Constant)}


def test_the_page_is_read_from_its_figures_not_from_prose() -> None:
    # R566 (owner, 2026-10-15 : « on doit comprendre par le graphique seul ») — the fit
    # verdict, the trigger paragraph and the ledger table are gone, and stay gone
    fns = _functions()
    gone = {"render_spend_revenue_fit", "_render_trigger_sentence", "_render_ledger"}
    assert not gone & set(fns), gone & set(fns)
    calls = {getattr(c.func, "attr", getattr(c.func, "id", ""))
             for c in ast.walk(fns["render_artist_money"]) if isinstance(c, ast.Call)}
    assert not calls & {"plotly_chart", "dataframe", "table", "caption"}, calls
    assert "imusician.roi_read" not in _i18n_keys_called(Path("src/dashboard/views/imusician.py")), (
        "the how-to-read caption is back")
