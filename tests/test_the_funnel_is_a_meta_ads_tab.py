"""« Tout mon funnel » is a tab of the Meta Ads page, not a menu entry.

Type: Hook
Uses: src.dashboard.utils.nav_sections, ast over src/dashboard/views/meta_ads_overview.py
Depends on: nothing (no database)
Persists in: nothing

R348 (2026-10-04, owner's screen review): « tout mon funnel, je sais pas ce que ça
apporte. Normalement on a des onglets à disposition pour ça. Il faudrait les mettre dans
les onglets Meta Ads ». The route `meta_x_spotify` survives for the links that target it.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.routes import ROUTES
from src.dashboard.utils.nav_sections import NAV_SECTIONS

OVERVIEW = (Path(__file__).resolve().parents[1]
            / "src" / "dashboard" / "views" / "meta_ads_overview.py")


def test_the_menu_no_longer_lists_the_funnel() -> None:
    keys = [key for _sid, _lbl, items in NAV_SECTIONS for _l, key in items]
    assert "meta_x_spotify" not in keys, "« Tout mon funnel » is back in the menu (R348)"
    assert "meta_x_spotify" in ROUTES, "the route is gone: pitch, recap and PDF links break"


def test_the_meta_ads_page_renders_the_funnel() -> None:
    # R476 — the sections are a registry; the « funnel » entry's renderer must reach
    # `render_funnel` (the journey of one campaign, ADR-032).
    from src.dashboard.views.meta_ads_overview import SECTIONS

    name = SECTIONS["funnel"].render.__name__
    tree = ast.parse(OVERVIEW.read_text(encoding="utf-8"))
    route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    calls = {getattr(c.func, "id", "") for c in ast.walk(route) if isinstance(c, ast.Call)}
    assert "render_funnel" in calls, "the cross view no longer offers the journey (R348)"


def test_the_journey_has_no_tabs() -> None:
    """R476 (owner W2 : « c'est flou ») — the four sub-tabs are gone; their content was
    redistributed to the perf and breakdowns sections."""
    body = (OVERVIEW.parent / "meta_x_spotify.py").read_text(encoding="utf-8")
    tree = ast.parse(body)
    tabs = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
            and getattr(c.func, "attr", "") == "tabs"]
    assert not tabs, "le parcours a repris des onglets (R476, W2)"
