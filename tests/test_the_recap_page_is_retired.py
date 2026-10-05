"""The « 📌 Récap » page is retired; its key still routes, to the home page (R379).

Type: Guard
Uses: src/dashboard/utils/nav_sections.py (NAV_SECTIONS), src/dashboard/routes.py (ROUTES)
Persists in: nothing

V26 (owner's screen review, 2026-10-05): the page drew nothing, it listed ten links. Old
links (mails, bookmarks) name `recap`, so the key stays as an alias — a retired page must
not become a dead end.
"""
from __future__ import annotations

import importlib.util

from src.dashboard.routes import ROUTES
from src.dashboard.utils.nav_sections import NAV_SECTIONS


def test_the_menu_no_longer_offers_the_recap() -> None:
    keys = [key for _sid, _label, items in NAV_SECTIONS for _l, key in items]
    assert keys, "the menu reads as empty — the extraction misses the items"
    assert "recap" not in keys, "« 📌 Récap » is back in the menu"


def test_an_old_recap_link_lands_on_the_home_page() -> None:
    assert ROUTES.get("recap") == ROUTES["home"], (
        "the `recap` key no longer routes home: an old link would be a dead end")
    assert importlib.util.find_spec("src.dashboard.views.recap") is None, (
        "the retired view is back in src/ — nothing routes to it")
