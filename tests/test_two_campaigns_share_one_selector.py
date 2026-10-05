"""Two Meta campaigns compare through ONE selector, at a comparable scale (R350).

Type: Test
Uses: pandas, pytest, inspect, ast, streamlit.testing.v1.AppTest (render half only)
Depends on: src/dashboard/utils/campaign_pair.py, src/dashboard/views/meta_ads_overview.py,
            src/dashboard/views/meta_creatives.py, src/dashboard/views/meta_breakdowns.py,
            a provisioned Postgres for the render half (skipped otherwise)
Persists in: nothing

The owner's request (screen review, 2026-10-04): on « Performance Globale », pick two
campaigns and read their global performance at a comparable scale; on « Visuels de
campagne » and « Qui a vu tes pubs », a second campaign filter. One shared selector whose
default is « none », so the single-campaign page is unchanged. The comparable scale:
totals on each campaign's OWN day 0 (first euro spent), the CPC recomputed from the two
running sums, breakdowns as shares of each campaign's own total.

Mutation record (2026-10-04) — each one applied, the file run, the tree restored; the
red tests below are the ones OBSERVED, not predicted:
  - `j0 = spent.min()` → `mine["day"].min()` (day 0 = first ROW, not first euro)
    → RED `test_day_zero_is_the_first_euro_spent_of_each_campaign`.
  - `.reindex(pd.date_range(...), fill_value=0)` removed (a pause day vanishes)
    → RED `test_a_pause_day_is_a_zero_on_the_clock`.
  - `cpc_cum` from the per-day spend/clicks instead of the two running sums → RED
    `test_the_running_cpc_comes_from_the_two_running_sums` (+3 tests sharing the frame,
    the overview render among them).
  - `share_pair` divides both sides by side A's total → RED
    `test_each_side_is_a_share_of_its_own_total`, `test_a_side_with_nothing_has_no_share`,
    both breakdowns render tests.
  - the 0 %-on-both-sides row filter removed → RED
    `test_a_label_at_zero_on_both_sides_is_not_a_row`.
  - `pair_options` keeps `first` among the choices → RED
    `test_the_second_list_offers_none_first_and_never_the_first_campaign` (+5 others).
  - `second_campaign` returns `pick` without the allowlist check → RED
    `test_a_pick_outside_the_list_is_refused`.
  - `{first, second} <= own` branch removed from `pair_colors` → RED
    `test_a_creative_of_both_campaigns_is_grey`.
  - the `second_campaign(...)` call replaced by a no-op in meta_breakdowns.show (since R399:
    the filter bar holds the one call) → RED
    `test_the_three_pages_call_the_one_selector` and both breakdowns render tests (they
    SKIPPED on the first run: `_pick_second` now fails when the page lists ≥2 campaigns).
  - `second = None and second_campaign(...)` in meta_creatives (the call still EXISTS, so
    the AST test stays green) → RED `test_the_creatives_page_colours_the_ranking_by_campaign`.
  - the scalar-subquery parameters of `_breakdown_frame` appended AFTER the UNION ones (the
    order shipped before R350) → RED
    `test_each_breakdown_parameter_lands_on_its_own_placeholder[performance]` and
    `test_the_breakdowns_page_compares_two_campaigns_as_shares[performance]`.
"""
from __future__ import annotations

import ast
import datetime as dt
import inspect
import math

import pandas as pd
import pytest

from src.dashboard.utils import campaign_pair as cp

D = dt.date


def _daily(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["campaign_name", "day", "spend", "link_clicks"])


def test_day_zero_is_the_first_euro_spent_of_each_campaign() -> None:
    got = cp.day0_cumulative(_daily([
        ("A", D(2024, 8, 30), 0, 3),      # a row before the first euro: not day 0
        ("A", D(2024, 8, 31), 10, 5), ("A", D(2024, 9, 1), 20, 5),
        ("B", D(2023, 1, 1), 4, 1), ("B", D(2023, 1, 2), 4, 1),
    ]), "A", "B")
    assert list(dict.fromkeys(got["campaign"])) == ["A", "B"]
    for name, spend in (("A", [10, 30]), ("B", [4, 8])):
        s = got[got["campaign"] == name]
        assert s["offset"].tolist() == [0, 1], f"{name} is not on its own day-0 clock"
        assert s["spend_cum"].tolist() == spend


def test_a_pause_day_is_a_zero_on_the_clock() -> None:
    got = cp.day0_cumulative(_daily([("A", D(2024, 1, 1), 5, 1),
                                     ("A", D(2024, 1, 4), 5, 1)]), "A", None)
    assert got["offset"].tolist() == [0, 1, 2, 3]
    assert got["spend_cum"].tolist() == [5, 5, 5, 10], "a pause day is not interpolated"


def test_the_running_cpc_comes_from_the_two_running_sums() -> None:
    got = cp.day0_cumulative(_daily([("A", D(2024, 1, 1), 10, 0),
                                     ("A", D(2024, 1, 2), 10, 4),
                                     ("A", D(2024, 1, 3), 10, 1)]), "A", None)
    cpc = got["cpc_cum"].tolist()
    assert math.isnan(cpc[0]), "no click yet: the CPC is undefined, not 0 or infinite"
    assert cpc[1:] == [5.0, 6.0]   # 20/4 then 30/5 — never the mean of daily CPCs (7.5)


def test_a_campaign_without_spend_gives_no_curve() -> None:
    got = cp.day0_cumulative(_daily([("A", D(2024, 1, 1), 0, 2)]), "A", None)
    assert got.empty and "offset" in got.columns


def test_each_side_is_a_share_of_its_own_total() -> None:
    a = pd.DataFrame({"dim_label": ["FR", "BE"], "value": [300.0, 100.0]})
    b = pd.DataFrame({"dim_label": ["FR", "BR"], "value": [10.0, 20.0]})
    got = cp.share_pair(a, b, "dim_label", "value").set_index("label")
    assert got["share_a"].sum() == pytest.approx(100) and got["share_b"].sum() == pytest.approx(100)
    assert got.loc["FR", "share_a"] == pytest.approx(75)
    assert got.loc["FR", "share_b"] == pytest.approx(100 / 3)
    assert got.loc["BE", "share_b"] == 0, "a label absent on one side is 0 % there"
    assert got.index[0] == "FR" and got.index[1] == "BR"   # FR 75 % > BR 66.7 %: biggest on either side first


def test_a_side_with_nothing_has_no_share() -> None:
    a = pd.DataFrame({"dim_label": ["FR"], "value": [5.0]})
    b = pd.DataFrame({"dim_label": ["FR"], "value": [0.0]})
    got = cp.share_pair(a, b, "dim_label", "value")
    assert got["share_a"].tolist() == [100.0] and got["share_b"].isna().all()


def test_a_label_at_zero_on_both_sides_is_not_a_row() -> None:
    a = pd.DataFrame({"dim_label": ["FR", "unknown"], "value": [5.0, 0.0]})
    b = pd.DataFrame({"dim_label": ["FR", "unknown"], "value": [3.0, 0.0]})
    assert cp.share_pair(a, b, "dim_label", "value")["label"].tolist() == ["FR"]


def test_the_second_list_offers_none_first_and_never_the_first_campaign() -> None:
    assert cp.pair_options(["A", "B", "C"], "B") == [None, "A", "C"]


def test_no_second_selector_without_one_first_campaign(monkeypatch) -> None:
    def _boom(*_a, **_k):
        raise AssertionError("the selector must not be drawn")
    monkeypatch.setattr(cp.st, "selectbox", _boom)
    assert cp.second_campaign(["A", "B"], "Toutes", key="k") is None
    assert cp.second_campaign(["A", "B"], None, key="k") is None
    assert cp.second_campaign(["A"], "A", key="k") is None   # nothing else to compare with


def test_the_default_is_none_so_the_page_is_unchanged(monkeypatch) -> None:
    seen = {}

    def _first_option(_label, options, **kw):
        seen.update(options=options, **kw)
        return options[0]
    monkeypatch.setattr(cp.st, "selectbox", _first_option)
    assert cp.second_campaign(["A", "B"], "A", key="k") is None
    assert seen["options"][0] is None and seen["key"] == "k"


def test_a_pick_outside_the_list_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(cp.st, "selectbox", lambda *_a, **_k: "Z'; DROP TABLE x;--")
    assert cp.second_campaign(["A", "B"], "A", key="k") is None
    monkeypatch.setattr(cp.st, "selectbox", lambda *_a, **_k: "B")
    assert cp.second_campaign(["A", "B"], "A", key="k") == "B"


def test_a_creative_of_both_campaigns_is_grey() -> None:
    rows = pd.DataFrame({"creative_name": ["x", "y", "z", "z"],
                         "campaign_name": ["A", "B", "A", "B"]})
    assert cp.pair_colors(["x", "y", "z"], rows, "A", "B") == [
        cp.PAIR_COLORS[0], cp.PAIR_COLORS[1], cp.BOTH_COLOR]


def test_the_three_pages_call_the_one_selector() -> None:
    """One helper, called ONCE: the page's filter bar (R399) — no section draws its own."""
    from src.dashboard.utils import meta_filter_bar
    from src.dashboard.views import meta_ads_overview, meta_breakdowns, meta_creatives

    def calls(mod) -> list:
        return [n for n in ast.walk(ast.parse(inspect.getsource(mod)))
                if isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", "")) == "second_campaign"]

    assert calls(meta_filter_bar), "the filter bar no longer offers the second campaign"
    for mod in (meta_ads_overview, meta_creatives, meta_breakdowns):
        assert not calls(mod), f"{mod.__name__} draws its own second-campaign selector again"
        read = {n.attr for n in ast.walk(ast.parse(inspect.getsource(mod)))
                if isinstance(n, ast.Attribute)}
        assert read & {"second", "scope"}, f"{mod.__name__} ignores the bar's pick"


class _SpyDb:
    def __init__(self) -> None:
        self.calls: list = []

    def fetch_df(self, sql, args):
        self.calls.append((sql, args))
        return pd.DataFrame()


def _bind(sql: str, args: tuple) -> str:
    """The SQL with each `%s` replaced, in order, by its parameter — what Postgres sees."""
    pieces = sql.split("%s")
    assert len(pieces) - 1 == len(args), "placeholder count differs from parameter count"
    return "".join(p + (repr(a) if i < len(args) else "")
                   for i, (p, a) in enumerate(zip(pieces, [*args, None])))


@pytest.mark.parametrize("family", ["performance", "engagement"])
def test_each_breakdown_parameter_lands_on_its_own_placeholder(family: str) -> None:
    """The compared campaign is read by the same query as the first: a parameter out of
    order there crashed the page as soon as ONE campaign was chosen (seen 2026-10-04)."""
    from src.dashboard.views.meta_breakdowns import _breakdown_frame
    db = _SpyDb()
    _breakdown_frame(db, 7, family, "campaign", "campaign_name", "Camp B",
                     " AND ad_account_id = %s", ("act_9",))
    bound = _bind(*db.calls[0])
    assert "artist_id = 7 AND ad_account_id = 'act_9'" in bound
    assert bound.count("campaign_name = 'Camp B'") == 3, bound
    assert "artist_id = 'Camp B'" not in bound and "campaign_name = 7" not in bound


# ── The render half: each page draws its pair with no error ─────────────────────
from tests.db_gate import db_ready  # noqa: E402

_needs_db = pytest.mark.skipif(not db_ready(), reason="render half needs the provisioned Postgres")


def _app(view: str):
    import os

    from streamlit.testing.v1 import AppTest

    from tests.render_harness import SCRIPT
    at = AppTest.from_string(SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=180)
    _clean(at)
    return at


def _clean(at) -> None:
    assert not at.exception, at.exception
    # The views wrap their body in `except Exception → st.error`: an error there is a crash.
    assert not [e.value for e in at.error], [e.value for e in at.error]


def _pick_second(at, key: str, offered: int | None = None):
    """`offered` = how many campaigns the page itself lists: with two or more, a missing
    second selector is the defect, not an absence of data — so it FAILS instead of skipping."""
    box = [s for s in at.selectbox if s.key == key]
    if not box or len(box[0].options) < 2:
        assert offered is None or offered < 2, f"{offered} campaigns listed and no {key} selector"
        pytest.skip(f"artist 1 has no second campaign to offer under {key}")
    box[0].select_index(1).run(timeout=180)
    _clean(at)
    return at


def _specs(at) -> list[dict]:
    import json
    return [json.loads(el.proto.spec) for el in at.get("plotly_chart")]


@_needs_db
def test_the_overview_draws_two_campaigns_on_the_day0_clock() -> None:
    at = _pick_second(_app("meta_ads_overview"), "meta_second")
    day0 = [s for s in _specs(at)
            if "J0" in str(((s.get("layout") or {}).get("xaxis") or {}).get("title", ""))]
    assert day0, "two campaigns chosen and no figure on the day-0 clock"
    names = {tr["name"] for tr in day0[0]["data"]}
    assert len(names) == 2, names
    for tr in day0[0]["data"]:
        assert tr["x"][0] == 0 and all(x >= 0 for x in tr["x"]), "a series is not on its day 0"


@_needs_db
def test_the_creatives_page_colours_the_ranking_by_campaign() -> None:
    at = _app("meta_creatives")
    first = [s for s in at.selectbox if s.key == "meta_campaign" and len(s.options) > 2]
    if not first:
        pytest.skip("artist 1 has fewer than two campaigns with creatives")
    first[0].select_index(1).run(timeout=180)
    _clean(at)
    at = _pick_second(at, "meta_second", offered=len(first[0].options) - 1)
    colours = set()
    for s in _specs(at):
        for tr in s["data"]:
            c = (tr.get("marker") or {}).get("color")
            if isinstance(c, list):
                colours |= set(c)
    assert colours & set(cp.PAIR_COLORS), "the ranking does not say which campaign a bar is"


@_needs_db
@pytest.mark.parametrize("family_index", [0, 1], ids=["performance", "engagement"])
def test_the_breakdowns_page_compares_two_campaigns_as_shares(family_index: int) -> None:
    at = _app("meta_breakdowns")
    if family_index:
        next(s for s in at.selectbox if s.key == "bd_family").select_index(family_index).run(timeout=180)
        _clean(at)
    camp = [s for s in at.selectbox if s.key == "meta_campaign"][0]
    if len(camp.options) < 2:   # only « Toutes »: the CI seed carries no Meta campaign
        pytest.skip("artist 1 has no campaign under meta_campaign")
    camp.select_index(1).run(timeout=180)
    _clean(at)
    at = _pick_second(at, "meta_second", offered=len(camp.options) - 1)   # minus « Toutes »
    pair = [s for s in _specs(at) if (s.get("layout") or {}).get("barmode") == "group"
            and (s["layout"].get("xaxis") or {}).get("ticksuffix") == " %"]
    if not pair:
        assert [i for i in at.info], "no share figure and no message saying why"
        return
    assert len({tr["name"] for tr in pair[0]["data"]}) == 2
    for tr in pair[0]["data"]:
        assert all(0 <= x <= 100 for x in tr["x"] if x is not None), "a share left 0–100 %"
