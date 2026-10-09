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
    # R476 (W13 II) — the cross view closes the platforms instead of following Spotify.
    assert keys[:5] == ["spotify_s4a_combined", "apple_music", "youtube", "soundcloud",
                        "meta_ads_overview"], keys
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


def test_every_section_of_the_registry_resolves() -> None:
    """R476 (ADR-032) — each entry names a label, a renderer and the filters it reads;
    a renderer's lazy imports must resolve, or the section crashes only when clicked."""
    import ast
    import importlib
    import inspect

    from src.dashboard.utils import meta_filter_bar as bar

    allowed = {bar.BAR_FULL, bar.BAR_JOURNEY, bar.BAR_UNDATED, bar.BAR_ACCOUNT, bar.BAR_NONE,
               None}
    assert list(SECTIONS) == ["funnel", "perf", "releases", "creatives", "breakdowns",
                              "instagram", "revenue"], list(SECTIONS)
    for key, entry in SECTIONS.items():
        assert isinstance(entry.label(), str) and entry.label(), key
        assert entry.bar in allowed, key
        tree = ast.parse(inspect.getsource(entry.render))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = importlib.import_module(node.module)
                for alias in node.names:
                    assert hasattr(mod, alias.name), f"{key}: {node.module}.{alias.name}"


def test_the_moved_charts_left_their_origin() -> None:
    """R476 — « un graphique déplacé disparaît de sa vue d'origine dans le même commit »."""
    import inspect

    from src.dashboard.views import apple_music, hypeddit, imusician

    assert "render_shazam_launches" not in inspect.getsource(apple_music.show)
    assert "render_campaign_stats" not in inspect.getsource(hypeddit.show)
    assert "render_break_even" not in inspect.getsource(imusician.show)
