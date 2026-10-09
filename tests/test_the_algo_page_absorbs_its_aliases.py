"""The algo page absorbs « Paramètres de mes campagnes » and « Prévisions revenus » (R405).

Type: Guard
Uses: src.dashboard.routes.ROUTES, src.dashboard.utils.nav_sections,
      src.dashboard.views.trigger_algo._sections, src/dashboard/views/saisie_s4a.py (AST)
Depends on: nothing
Persists in: nothing

Owner's notes V73/V74 (2026-10-05): the two pages became sections of the algo page.
Their keys stay as ALIASES — mails and PDFs link to them — and land on their section;
the realised outcomes and the model's bet are ONE module drawn on the Free S4A entry
page as well, so the paywall never hides the outcome entry.

Mutations, 2026-10-05:
  - `revenue_forecast` routed back to `views.revenue_forecast` → RED (alias);
  - `arrival_section` answering a non-alias key with a section → RED;
  - `meta_campaign_settings` put back in the Premium nav → RED;
  - the `render_outcomes(db, artist_id)` call dropped from saisie_s4a → RED (until R481,
    2026-10-09, which moved it to the algo page only — the guard is inverted).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.routes import ROUTES
from src.dashboard.views.trigger_algo._sections import (ALIAS_SECTION, arrival_section,
                                                        section_keys)


@pytest.mark.parametrize("alias", sorted(ALIAS_SECTION))
def test_each_old_key_routes_to_the_algo_page(alias: str) -> None:
    assert ROUTES[alias] == "views.trigger_algo", f"« {alias} » no longer reaches the algo page"


@pytest.mark.parametrize("alias,section", sorted(ALIAS_SECTION.items()))
def test_an_alias_points_at_a_section_the_page_draws(alias: str, section: str) -> None:
    assert section in section_keys()
    assert arrival_section(alias) == section
    # A run that did not arrive by an alias (app.py sets None) shows no banner.
    assert arrival_section(None) is None
    assert arrival_section("trigger_algo") is None


def test_the_premium_menu_no_longer_lists_the_absorbed_pages() -> None:
    from src.dashboard.utils.nav_sections import NAV_SECTIONS

    keys = {key for _id, _hdr, items in NAV_SECTIONS for _label, key in items}
    assert "trigger_algo" in keys, "the scan reads no menu"
    assert not keys & set(ALIAS_SECTION), f"absorbed pages still in the menu: {keys & set(ALIAS_SECTION)}"


def test_the_outcomes_live_on_the_algo_page_only() -> None:
    """R481 (W4, 2026-10-09) reverses R405's second site : ONE place, the algo page."""
    def calls(path: str) -> list:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        return [c for c in ast.walk(tree) if isinstance(c, ast.Call)
                and getattr(c.func, "id", getattr(c.func, "attr", "")) == "render_outcomes"]
    assert not calls("src/dashboard/views/saisie_s4a.py"), (
        "the S4A entry page draws the outcomes again — W4 moved them to the algo page")
    assert calls("src/dashboard/views/trigger_algo/router.py"), (
        "the algo page no longer draws the outcome entry")
