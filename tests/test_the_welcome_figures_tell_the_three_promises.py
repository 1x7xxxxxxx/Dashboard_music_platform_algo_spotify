"""R455 — the three welcome figures draw what the owner asked for, read off the built figure.

Type: Test
Uses: tools/dev/make_example_charts (dashboard_global, discover_weekly_prediction, meta_x_s4a)
Depends on: matplotlib (Agg)

Owner, 2026-10-07 (voice comments C1-C3):
- C1 « Shazam devient la 5ᵉ courbe montante » of the multi-platform figure;
- C2 « trois courbes de pourcentage de déclencher, uniquement en prévision » — DW,
  Release Radar, Radio, on a 0-100 % axis, nothing measured (every line dashed);
- C3 « optimiser le budget Meta Ads pour maximiser les streams » — the campaign figure
  says how much to put back, so the advised budget is drawn after the last observed day.

The figure is captured at `_save`, so the test reads the Axes the PNG is made of, not
the source text that builds it.

Mutation record (2026-10-07): Shazam removed from the stack → red; Radio drawn solid →
red; the advised-budget bars removed → red.
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


def test_shazam_is_the_fifth_stacked_band(built):
    (ax,) = built("dashboard_global").axes
    bands = [c for c in ax.collections if type(c).__name__ in {"PolyCollection", "FillBetweenPolyCollection"}]
    assert len(bands) == 5, f"{len(bands)} stacked bands, the owner asked for five"
    assert "Shazam" in _texts(ax)


def test_the_prediction_is_three_forecast_probabilities(built):
    (ax,) = built("discover_weekly_prediction").axes
    curves = [ln for ln in ax.lines if len(ln.get_xdata()) > 2]
    assert len(curves) == 3
    assert all(ln.get_linestyle() != "-" for ln in curves), "a solid line reads as measured"
    assert ax.get_ylim() == (0, 100)
    labels = _texts(ax)
    assert all(name in labels for name in ("Discover Weekly", "Release Radar", "Radio"))


def test_the_campaign_figure_advises_a_budget_after_today(built):
    fig = built("meta_x_s4a")
    ax, axe = fig.axes
    last_observed = max(ln.get_xdata()[-1] for ln in ax.lines if ln.get_linestyle() == "-"
                        and len(ln.get_xdata()) > 2)
    advised = [p for p in axe.patches if p.get_x() > last_observed and p.get_height() > 0]
    assert advised, "no budget drawn after the last observed day"
    assert "budget" in ax.get_title(loc="left").lower()
