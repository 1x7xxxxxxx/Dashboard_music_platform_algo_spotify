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
    # R555 — one calendar figure, the effect per campaign, the releases at equal age.
    for name in ("_render_timeline", "_render_effect_duration", "render_release_cohort"):
        assert name in calls, f"« {name} » is not in the chronology"


def test_the_funnel_section_holds_the_totals_and_the_comparison() -> None:
    calls = _called(_function(VIEWS / "meta_ads_overview.py",
                              SECTIONS["entonnoir"].render.__name__))
    for name in ("render_funnel", "_render_campaign_totals", "render_compare"):
        assert name in calls, f"« {name} » is not in the funnel section"


def test_the_effect_duration_draws_the_curve_only() -> None:
    """Fiche 27: one figure, the curve — the bars per wave are gone (R555: per campaign)."""
    calls = _called(_function(VIEWS / "meta_ads_overview.py", "_render_effect_duration"))
    assert calls.count("plotly_chart") == 1, calls
    assert "make_subplots" not in calls


def test_the_daily_figure_no_longer_carries_the_targeting_ring() -> None:
    """Fiche 30: the ring by optimisation goal left the daily figure (R555: the timeline)."""
    calls = _called(_function(VIEWS / "meta_ads_overview.py", "_render_timeline"))
    assert "spend_ring" not in calls
    assert calls.count("plotly_chart") == 1, calls


def test_the_breakdowns_draw_no_map() -> None:
    """Fiches 32 and 34: the country Pareto carries the CPR the maps did not."""
    for fn in ("_render_performance", "_render_engagement"):
        assert "choropleth" not in _called(_function(VIEWS / "meta_breakdowns.py", fn)), fn


def test_the_settings_section_has_no_optimisation_panel() -> None:
    """R568 removed the separate goal Pareto of the cross view; R597 (owner, 2026-10-15)
    removed the « Optimisation de l'ad set » panel of the best-settings tool too. Button and
    objective stay, read per campaign."""
    tree = ast.parse((VIEWS / "meta_ads_overview.py").read_text(encoding="utf-8"))
    assert "_render_goal_pareto" not in {n.name for n in tree.body
                                         if isinstance(n, ast.FunctionDef)}
    import src.dashboard.views.meta_creatives as mc
    assert not hasattr(mc, "_Q_GOAL")
    panels = _function(VIEWS / "meta_creatives.py", "_ad_setting_panels")
    assert "_Q_AXE" in {n.id for n in ast.walk(panels) if isinstance(n, ast.Name)}
    assert "objective" in mc._Q_AXE["objectif"]
    assert all("campaign_name" in q for q in mc._Q_AXE.values())
