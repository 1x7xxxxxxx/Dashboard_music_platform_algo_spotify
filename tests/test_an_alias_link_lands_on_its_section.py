"""An old page key in a link (`?page=<alias>`) lands on the page that holds it (R405).

Type: Guard
Uses: src.dashboard.routes (ROUTES, PAGE_ALIASES, resolve_alias), src.dashboard.utils.nav_sections,
      src/dashboard/app.py (AST), src.dashboard.views.trigger_algo (render)
Depends on: live Postgres for the render (skipped without)
Persists in: nothing

The defect, 2026-10-05: R378 and R405 kept the retired page keys in `ROUTES` « so that
the links in mails and PDFs keep working ». They did not: app.py's URL handler accepts a
`?page=` only if it is in the menu, and `resolve_nav_page` sends any `_nav_page` outside
the menu home. Seven aliases — every link to the old Meta pages, to « Prévisions
revenus » and « Paramètres de mes campagnes » — opened the home page. `test_every_route
_resolves` was green: it checks a key reaches a module, not that a URL reaches the key.

Mutations, 2026-10-05:
  - `revenue_forecast` dropped from PAGE_ALIASES → RED (unlisted alias);
  - the `resolve_alias` line moved below the menu filter in app.py → RED (order);
  - the banner's `ALIAS_ARRIVAL_KEY` read replaced by the old `_page_rendered_last` → RED (render).
  - `resolve_alias` dropped from `navigation.goto` → RED.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from src.dashboard.routes import ALIAS_ARRIVAL_KEY, PAGE_ALIASES, ROUTES, resolve_alias
from src.dashboard.utils.nav_sections import NAV_SECTIONS
from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_MENU = {key for _id, _hdr, items in NAV_SECTIONS for _label, key in items}


def test_every_route_off_the_menu_that_reuses_a_page_is_a_listed_alias() -> None:
    menu_modules = {ROUTES[k]: k for k in _MENU if k in ROUTES}
    shadows = sorted(k for k in set(ROUTES) - _MENU if ROUTES[k] in menu_modules)
    assert shadows, "no alias at all — the scan reads no route"
    missing = [k for k in shadows if k not in PAGE_ALIASES]
    assert not missing, (
        f"route keys that reuse a menu page's module but no `?page=` can reach: {missing} "
        "— name them in routes.PAGE_ALIASES, or app.py drops their links")


@pytest.mark.parametrize("alias,target", sorted(PAGE_ALIASES.items()))
def test_an_alias_targets_a_menu_page_with_the_same_module(alias: str, target: str) -> None:
    assert target in _MENU, f"« {alias} » → « {target} », which the menu does not offer"
    assert ROUTES[alias] == ROUTES[target]
    assert resolve_alias(alias) == (target, alias)
    assert resolve_alias(target) == (target, None)


def test_app_translates_the_alias_before_its_menu_filter() -> None:
    src = Path("src/dashboard/app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "resolve_alias"]
    filters = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(getattr(t_, "id", "") == "_nav_keys" for t_ in n.targets)]
    assert calls and filters, "app.py no longer has the alias call or the menu filter"
    assert min(calls) < min(filters), "the alias is translated AFTER the menu filter drops it"


@pytest.mark.skipif(not db_ready(), reason="renders the algo page against the live DB")
@pytest.mark.parametrize("alias", ["revenue_forecast", "meta_campaign_settings"])
def test_the_arriving_run_says_where_the_old_page_went(alias: str) -> None:
    from streamlit.testing.v1 import AppTest

    script = TENANT_SCRIPT.format(root=os.getcwd(), view="trigger_algo", artist_id=1)
    at = AppTest.from_string(script)
    at.session_state[ALIAS_ARRIVAL_KEY] = alias
    at.run(timeout=300)
    assert not at.exception, at.exception
    banners = [i.value for i in at.info if "fait désormais partie" in i.value]
    assert len(banners) == 1, f"arriving by « {alias} », no banner: {[i.value[:60] for i in at.info]}"
    at.session_state[ALIAS_ARRIVAL_KEY] = None
    at.run(timeout=300)
    assert not [i for i in at.info if "fait désormais partie" in i.value], "the banner stays"


def test_goto_translates_an_alias_too() -> None:
    """`goto("upload_csv")` — the « add my S4A numbers » button — opened the home page."""
    tree = ast.parse(Path("src/dashboard/utils/navigation.py").read_text(encoding="utf-8"))
    goto = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "goto")
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "resolve_alias"
               for n in ast.walk(goto)), "goto() writes an alias key resolve_nav_page sends home"
