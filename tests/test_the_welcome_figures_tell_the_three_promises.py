"""R455 — the three welcome figures draw what the owner asked for, read off the built figure.

Type: Test
Uses: tools/dev/make_example_charts (dashboard_global, discover_weekly_prediction, meta_x_s4a,
      meta_x_algo)
Depends on: matplotlib (Agg)

Owner, 2026-10-07 (voice comments C1-C3):
- C1 « Shazam devient la 5ᵉ courbe montante » of the multi-platform figure;
- C2 « trois courbes de pourcentage de déclencher, uniquement en prévision » — DW,
  Release Radar, Radio, on a 0-100 % axis, nothing measured (every line dashed);
- C3 « optimiser le budget Meta Ads pour maximiser les streams » — the campaign figure
  says how much to put back, so the advised budget is drawn after the last observed day.

The figure is captured at `_save`, so the test reads the Axes the PNG is made of, not
the source text that builds it.

Owner, 2026-10-11 (X3 II, R515): the CPR over the Meta band; the prediction measured
(solid) then forecast (dashed) with Release Radar's bump after its trigger; the hatched
advised bars replaced by two annotations placed on the model's windows (`_verdict._PHASES`).

Mutation record (2026-10-07): Shazam removed from the stack → red; Radio drawn solid →
red; the advised-budget bars removed → red.
(2026-10-11, R515): Release Radar held at 100 % → red; « couper » moved to day 30 → red;
the CPR made flat → red; hatched Meta bars → red.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "dev" / "make_example_charts.py"


@pytest.fixture()
def built(monkeypatch):
    spec = importlib.util.spec_from_file_location("_r455_charts", _SCRIPT)
    charts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(charts)
    figures = {}
    monkeypatch.setattr(charts, "_save", lambda fig, name: figures.setdefault(name, fig))

    def build(maker: str):
        getattr(charts, maker)()
        (fig,) = figures.values()
        figures.clear()
        return fig
    return build


def _texts(ax) -> str:
    return " ".join(t.get_text() for t in ax.texts) + " " + ax.get_title(loc="left")


def test_shazam_and_hypeddit_are_stacked_and_meta_spend_sits_apart(built):
    """R455 : Shazam is the 5th band. R480 (W3) : Hypeddit clicks the 6th ; Meta is in
    euros, another unit, so it gets its own panel instead of joining the stack."""
    ax, axm, *_ = built("dashboard_global").axes
    bands = [c for c in ax.collections if type(c).__name__ in {"PolyCollection", "FillBetweenPolyCollection"}]
    assert len(bands) == 6, f"{len(bands)} stacked bands, the owner asked for six"
    assert "Shazam" in _texts(ax) and "Hypeddit" in _texts(ax)
    assert axm.patches and "Meta" in _texts(axm), "Meta spend has no panel of its own"


def test_the_overview_overlays_a_falling_cpr_on_the_meta_band(built):
    """R515 (X3 II) : the CPR on its own axis over the Meta band. R533 (2026-10-12) : it
    FALLS — the promise is a cost per result that goes down, not one that wanders."""
    fig = built("dashboard_global")
    _ax, axm, axc = fig.axes
    (cpr,) = [ln for ln in axc.lines if len(ln.get_xdata()) > 2]
    y = cpr.get_ydata()
    assert 0 < y.min() and y.max() <= 0.36, "CPR leaves its 0-0,36 € axis"
    assert y[:7].mean() - y[-7:].mean() > 0.08, "the CPR does not fall over the 90 days"
    assert axc.get_shared_x_axes().joined(axc, axm), "the CPR is not drawn over the Meta band"
    assert "CPR" in _texts(axm)


def test_the_prediction_is_measured_then_forecast_with_the_release_radar_bump(built):
    """R455 three probabilities; R515 (X3 II) : measured solid, forecast dashed, and
    Release Radar's bump AFTER its trigger — it touches 100 % in the measured part, then
    the forecast brings it back down."""
    (ax,) = built("discover_weekly_prediction").axes
    curves = [ln for ln in ax.lines if len(ln.get_xdata()) > 2]
    measured = [ln for ln in curves if ln.get_linestyle() == "-"]
    forecast = [ln for ln in curves if ln.get_linestyle() != "-"]
    assert len(measured) == 3 and len(forecast) == 3
    assert all(ln.get_xdata().max() <= 0 for ln in measured), "a measured line runs into the future"
    assert all(ln.get_xdata().min() >= 0 for ln in forecast), "a forecast line runs into the past"
    rr_past, rr_future = measured[0].get_ydata(), forecast[0].get_ydata()
    assert rr_past.max() >= 100, "Release Radar is not triggered in the measured part"
    assert rr_future[-1] < 50, "no bump: Release Radar never comes back down"
    assert ax.get_ylim() == (0, 100)
    labels = _texts(ax)
    assert all(name in labels for name in ("Discover Weekly", "Release Radar", "Radio"))


def test_discover_weekly_and_radio_each_get_a_forecast_date(built):
    """R533 (2026-10-12) : « les prédictions DW et Radio » — each forecast stops at the
    100 % floor, a hollow marker sits there, and « prévu J+n » names the day."""
    (ax,) = built("discover_weekly_prediction").axes
    forecast = [ln for ln in ax.lines if len(ln.get_xdata()) > 2 and ln.get_linestyle() != "-"]
    stopped = [ln for ln in forecast if ln.get_ydata()[-1] >= 100 - 1e-6]
    assert len(stopped) == 2, f"{len(stopped)} forecasts stop at the floor, expected DW + Radio"
    hollow = [ln for ln in ax.lines if len(ln.get_xdata()) == 1
              and ln.get_markerfacecolor() != ln.get_markeredgecolor()]
    assert sorted(ln.get_xdata()[0] for ln in hollow) == sorted(
        ln.get_xdata()[-1] for ln in stopped), "a predicted date has no hollow marker"
    dates = [t.get_text() for t in ax.texts if "prévu J+" in t.get_text()]
    assert len(dates) == 2 and any("Discover Weekly" in d for d in dates) and any(
        "Radio" in d for d in dates), dates


def test_the_fourth_figure_draws_the_meta_budget_under_the_chances(built):
    """R533 : « une 4ᵉ figure qui fusionne les chances et le budget Meta » — bars of spend
    (measured, then advised) under the DW and Radio curves, in a colour YouTube does not
    already wear."""
    from matplotlib.colors import to_hex

    charts_mod = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("_r533_c", _SCRIPT))
    charts_mod.__spec__.loader.exec_module(charts_mod)
    ax, axe = built("meta_x_algo").axes
    alphas = {round(p.get_alpha() or 1, 2) for p in axe.patches}
    assert len(alphas) == 2, f"spent and advised bars are not told apart: {alphas}"
    assert {to_hex(p.get_facecolor()) for p in axe.patches} == {charts_mod.META}
    assert charts_mod.META.lower() != charts_mod.ORANGE.lower(), "Meta wears YouTube's red"
    curves = [ln for ln in ax.lines if len(ln.get_xdata()) > 2]
    assert any(ln.get_linestyle() == "-" for ln in curves) and any(
        ln.get_linestyle() != "-" for ln in curves), "no measured-then-forecast curve"
    labels = _texts(ax)
    assert "Discover Weekly" in labels and "Radio" in labels and "relancer" in labels


def test_the_campaign_advice_follows_the_model_windows(built):
    """R515 (X3 II) : the hatched « conseillé » bars are gone ; two annotations sit on the
    model's windows — cut where Discover Weekly triggers (inside 35-90 d), relaunch
    before the Radio window (before 90 d, in the forecast)."""
    from src.dashboard.views.trigger_algo._common._verdict import _PHASES

    fig = built("meta_x_s4a")
    ax, axe = fig.axes
    assert not [p for p in axe.patches if p.get_hatch()], "the hatched advised bars are back"
    dw = next(p for p in _PHASES if "Discover Weekly" in p[2])
    advice = {a.get_text().replace("\n", " "): a.xy[0] for a in ax.texts if hasattr(a, "xy")}
    cut = next(x for t, x in advice.items() if t.startswith("couper"))
    relaunch = next(x for t, x in advice.items() if t.startswith("relancer"))
    assert dw[0] <= cut < dw[1], f"« couper » at day {cut}, outside the DW window {dw[:2]}"
    today = max(ln.get_xdata()[-1] for ln in ax.lines if ln.get_linestyle() == "-"
                and len(ln.get_xdata()) > 2)
    assert today < relaunch < dw[1], f"« relancer » at day {relaunch}, not before the Radio window"
    assert "Discover Weekly" in " ".join(advice) and "Radio" in " ".join(advice)
    assert "budget" in ax.get_title(loc="left").lower()
