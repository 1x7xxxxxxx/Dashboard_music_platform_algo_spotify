"""The cross view reads top to bottom in five sections; four figures left it (R554).

Type: Guard
Uses: ast, src.dashboard.views.meta_ads_overview
Depends on: src/dashboard/views/meta_ads_overview.py, src/dashboard/views/meta_breakdowns.py
Persists in: nothing (no database)

Owner's note Y2 (2026-10-13), ADR-033 decision 2: seven sections became five — when,
how much at each step, which creative and setting, who, and the organic side. The
figures retired with it answered no question of their section:

* fiche 27 — the bars per wave (budget, streams gained, € per stream): a second
  chronology of the waves the curve already draws;
* fiche 30 — the targeting ring by optimisation goal: R557 rebuilds a « best settings »
  tool in « Créas & réglages »;
* fiches 32 and 34 — the two choropleths: the country Pareto beside them names the same
  countries WITH the CPR.

Each property is read in the code that draws, not in a list that describes it.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.views.meta_ads_overview import (
    ALIAS_SECTION, DEFAULT_SECTION, SECTIONS)

VIEWS = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _called(node: ast.AST) -> list[str]:
    out = []
    for c in ast.walk(node):
        if isinstance(c, ast.Call):
            f = c.func
            out.append(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    return out


def test_the_five_sections_in_reading_order() -> None:
    assert list(SECTIONS) == ["chrono", "entonnoir", "creas", "audiences", "instagram"]
    assert DEFAULT_SECTION == "entonnoir"
    assert set(ALIAS_SECTION.values()) <= set(SECTIONS)


def test_the_chronology_holds_every_reading_with_a_calendar() -> None:
    calls = _called(_function(VIEWS / "meta_ads_overview.py", SECTIONS["chrono"].render.__name__))
    for name in ("_show_meta_ads", "_render_campaign_waves", "render_release_cohort",
                 "render_shazam_launches"):
        assert name in calls, f"« {name} » is not in the chronology"


def test_the_funnel_section_holds_the_totals_and_the_comparison() -> None:
    calls = _called(_function(VIEWS / "meta_ads_overview.py",
                              SECTIONS["entonnoir"].render.__name__))
    for name in ("render_funnel", "_render_campaign_totals", "render_compare",
                 "render_campaign_stats"):
        assert name in calls, f"« {name} » is not in the funnel section"


def test_the_waves_draw_the_curve_only() -> None:
    """Fiche 27: one figure, the curve — the bars per wave are gone."""
    calls = _called(_function(VIEWS / "meta_ads_overview.py", "_render_campaign_waves"))
    assert calls.count("plotly_chart") == 1, calls
    assert "make_subplots" not in calls


def test_the_daily_figure_no_longer_carries_the_targeting_ring() -> None:
    """Fiche 30: the ring by optimisation goal left `_show_meta_ads`."""
    calls = _called(_function(VIEWS / "meta_ads_overview.py", "_show_meta_ads"))
    assert "spend_ring" not in calls
    assert calls.count("plotly_chart") == 1, calls


def test_the_breakdowns_draw_no_map() -> None:
    """Fiches 32 and 34: the country Pareto carries the CPR the maps did not."""
    for fn in ("_render_performance", "_render_engagement"):
        assert "choropleth" not in _called(_function(VIEWS / "meta_breakdowns.py", fn)), fn


def test_the_settings_section_reads_the_optimisation_goal() -> None:
    """Fiche 30's data stays read: `v_meta_adset_daily` feeds the first « best setting »."""
    calls = _called(_function(VIEWS / "meta_ads_overview.py", SECTIONS["creas"].render.__name__))
    assert "_render_goal_pareto" in calls
    assert "pareto_spend_cpr" in _called(_function(VIEWS / "meta_ads_overview.py",
                                                   "_render_goal_pareto"))
