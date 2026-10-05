"""The Meta page draws ONE filter bar — account, campaign, period — and no section a second (R399).

Type: Guard
Uses: src/dashboard/views/meta_*.py + instagram.py + utils/campaign_compare.py (AST),
      src.dashboard.views.meta_ads_overview (render)
Depends on: live Postgres for the render (skipped without)
Persists in: nothing

Owner's demand (2026-10-05): « les mêmes filtres à chaque fois ». Before R399 the four
Meta sections drew four account widgets, three campaign lists and two second-campaign
pickers, and the creative timeline its own period. Two properties are held:

  1. outside `utils/meta_filter_bar.py`, every selector in these files carries a constant
     key listed below WITH the reason it is not a filter of the page — a new selector
     must either read the bar or argue its case here;
  2. rendered, each section shows the bar's campaign selector once and no period widget
     besides the bar's; Instagram (organic) shows none and says it is outside.

Mutations, 2026-10-05:
  - `key="tl"` period put back in the creative timeline → (1) RED (unlisted call) and
    (2) RED (`tl_1_preset` rendered in « Visuels »);
  - `bd_adset` removed from the allowlist → (1) RED;
  - `say_instagram_is_outside()` dropped from `show()` → (2) RED.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from src.dashboard.utils.meta_filter_bar import PERIOD_KEY
from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_FILES = [Path("src/dashboard/views") / f"{n}.py" for n in (
    "meta_ads_overview", "meta_x_spotify", "meta_creatives", "meta_breakdowns", "instagram")]
_FILES.append(Path("src/dashboard/utils/campaign_compare.py"))

_SELECTORS = {"selectbox", "multiselect", "segmented_control", "radio", "pills", "date_input",
              "slider", "select_slider", "smart_period_filter", "period", "span",
              "account_scope", "second_campaign"}

# key → why it is not a filter of the page.
_ALLOWED = {
    "meta_overview_section": "navigation between the sections",
    "tgt_dim": "the dimension a chart is split by, not a filter",
    "bd_family": "which metric family the breakdowns show",
    "bd_adset": "drill-down INSIDE the bar's campaign",
    "bd_ad": "drill-down INSIDE the bar's campaign",
    "rank_sort": "sort order of the ranking",
    "tl_creative": "which creative's timeline, inside the bar's scope",
    "funnel_creative": "which creative's funnel, inside the bar's scope",
    "fatigue_creative": "which creative's fatigue curve",
    "cmp_funnel": "which songs are compared, not a Meta filter",
    "ig_community": "Instagram is organic: outside the bar, its charts keep their period",
    "ig_media": "Instagram is organic: outside the bar, its charts keep their period",
}


def _module_constants(tree: ast.Module) -> dict[str, str]:
    return {n.targets[0].id: n.value.value for n in tree.body
            if isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}


def _selector_keys(path: Path) -> list[tuple[int, str, str | None]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    consts = _module_constants(tree)
    out = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        name = getattr(call.func, "id", getattr(call.func, "attr", ""))
        if name not in _SELECTORS:
            continue
        key = next((k.value for k in call.keywords if k.arg == "key"), None)
        if isinstance(key, ast.Constant):
            key = key.value
        elif isinstance(key, ast.Name):
            key = consts.get(key.id)
        else:
            key = None
        out.append((call.lineno, name, key))
    return out


def test_no_section_draws_its_own_filter() -> None:
    strays = [f"{p}:{line} {name}(key={key!r})" for p in _FILES
              for line, name, key in _selector_keys(p) if key not in _ALLOWED]
    assert not strays, (
        "a Meta section draws a selector that is neither the page's filter bar nor "
        f"allowlisted with a reason — read `bar` instead, or argue it in _ALLOWED: {strays}")


def test_the_allowlist_has_no_dead_entry() -> None:
    used = {key for p in _FILES for _, _, key in _selector_keys(p)}
    assert set(_ALLOWED) <= used, f"allowlisted keys no selector carries: {set(_ALLOWED) - used}"


def _walk(node):
    for child in getattr(node, "children", {}).values():
        yield child
        yield from _walk(child)


@pytest.mark.skipif(not db_ready(), reason="renders the Meta page against the live DB")
def test_each_section_renders_the_one_bar() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="meta_ads_overview",
                                                  artist_id=1))
    at.run(timeout=180)
    for section in ("funnel", "perf", "creatives", "breakdowns", "instagram"):
        at.segmented_control(key="meta_overview_section").set_value(section).run(timeout=180)
        assert not at.exception, (section, at.exception)
        keys = [getattr(w, "key", None) for w in _walk(at._tree)]
        # The bar's own free period (`meta_period_*`) is drawn when no campaign is
        # chosen — the CI's empty base, red on 7c02a42c when it was counted as a stray.
        periods = sorted(k for k in keys if k and k.endswith("_preset")
                         and not k.startswith(("ig_", PERIOD_KEY)))
        assert not periods, f"« {section} » draws a period of its own: {periods}"
        campaign = keys.count("meta_campaign")
        if section == "instagram":
            assert campaign == 0, "Instagram (organic) shows the ad campaign filter"
            assert any("Instagram organique" in c.value for c in at.caption), (
                "Instagram does not say it is outside the bar")
        else:
            assert campaign == 1, f"« {section} » shows the campaign filter {campaign} times"


@pytest.mark.skipif(not db_ready(), reason="renders the Meta page against the live DB")
def test_the_bars_free_period_is_not_a_stray() -> None:
    """« Toutes » draws the bar's free period — the CI's empty base does it by default."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="meta_ads_overview",
                                                  artist_id=1))
    at.run(timeout=180)
    at.segmented_control(key="meta_overview_section").set_value("perf").run(timeout=180)
    at.selectbox(key="meta_campaign").set_value("Toutes").run(timeout=180)
    assert not at.exception, at.exception
    keys = [getattr(w, "key", None) for w in _walk(at._tree)]
    assert any(k and k.startswith(PERIOD_KEY) for k in keys), "the free period is not drawn"
    strays = [k for k in keys if k and k.endswith("_preset")
              and not k.startswith(("ig_", PERIOD_KEY))]
    assert not strays, strays
