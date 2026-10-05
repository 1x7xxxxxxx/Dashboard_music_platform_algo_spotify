"""The Vue croisée is one page; the pages it absorbed are its sections and alias to it (R378).

Type: Guard
Uses: src.dashboard.routes, src.dashboard.utils.nav_sections, views.meta_ads_overview
Depends on: nothing (no database)
Persists in: nothing

Owner's screen review, 2026-10-05 (V8, V29, V30, V35, V36, V70): « Publicité Meta Ads »,
« Visuels de campagne », « Qui a vu tes pubs » and « Instagram » become ONE cross view at
the head of Analytics. A merge is two properties — gone from the menu AND reachable —
so each old route must land on the page AND open the section it used to be.
"""
from __future__ import annotations

from src.dashboard.routes import ROUTES
from src.dashboard.utils.nav_sections import NAV_SECTIONS
from src.dashboard.views.meta_ads_overview import ALIAS_SECTION, SECTIONS, arrival_section

# Written out, not read from ALIAS_SECTION: a map checked against itself proves nothing.
_EXPECTED = {"meta_x_spotify": "funnel", "meta_creatives": "creatives",
             "meta_breakdowns": "breakdowns", "instagram": "instagram"}
_ABSORBED = tuple(_EXPECTED)


def _analytics() -> list[str]:
    return next(items for sid, _lbl, items in NAV_SECTIONS if sid == "analytics")


def test_the_analytics_menu_is_the_platforms_and_the_cross_view() -> None:
    keys = [key for _l, key in _analytics()]
    assert keys[:5] == ["spotify_s4a_combined", "meta_ads_overview", "apple_music",
                        "youtube", "soundcloud"], keys
    assert not set(_ABSORBED) & set(keys), "an absorbed page is back in the menu"


def test_every_absorbed_route_is_an_alias_to_the_cross_view() -> None:
    for key in _ABSORBED:
        assert ROUTES[key] == ROUTES["meta_ads_overview"], key


def test_every_alias_opens_the_section_it_named() -> None:
    assert set(ALIAS_SECTION) == set(_ABSORBED)
    for key, section in _EXPECTED.items():
        assert section in SECTIONS, section
        assert arrival_section(key) == section


def test_an_alias_does_not_override_a_later_click() -> None:
    # R405: app.py sets the alias on the ARRIVING run only (the URL mirror then rewrites
    # `?page=`); a later run carries no alias, so the control is never overridden.
    from src.dashboard.routes import resolve_alias

    assert resolve_alias("meta_creatives") == ("meta_ads_overview", "meta_creatives")
    assert resolve_alias("meta_ads_overview") == ("meta_ads_overview", None)
    assert arrival_section(None) is None
    assert arrival_section("meta_ads_overview") is None
