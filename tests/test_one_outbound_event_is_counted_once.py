"""One Hypeddit outbound click is ONE Meta result — never the sum of its names.

Type: Hook (guard)
Uses: src.collectors._meta_parsers, src.collectors._meta_insight_fetch, tests.db_gate
Persists in: nothing

Measured 2026-09-26 on spotify_etl_review, meta_insights_performance_day, artist_id=1
(the sandbox tenant 18 is a byte-identical mirror and is left out of every figure): on
the 196 day-rows with custom_conversions > 0, results / custom_conversions lies between
1.977 and 2.574, exactly 2.00 on 118 rows — 23 139 results for 11 356 outbound clicks.
`_results_for_goal` summed EVERY action_type starting with 'offsite_conversion', and
Meta reports the one outbound event under more than one such name.

Which second name(s) is NOT observed: no raw `actions` payload was ever stored. So the
fixtures below do not assert what Meta sends; they assert the PROPERTY the fix relies
on — when an 'offsite_conversion.custom*' family is present it is the result, whatever
other offsite family sits next to it. The second family is parametrised over several
plausible names precisely so no single guess becomes ground truth.

Every fixture in tests/test_meta_ads_collector.py carried ONE offsite family per
insight, which is why the union and the single family could never be told apart.

Class: a-prefix-sum-that-counts-one-event-under-two-names.
"""
from __future__ import annotations

import pytest

from src.collectors._meta_insight_fetch import _MetaInsightFetchMixin
from src.collectors._meta_parsers import _extract_perf, _results_for_goal
from tests.db_gate import requires_live_db

pytestmark = pytest.mark.xdist_group("meta-ads-collector")

# Plausible second names for the same event. NOT an observation — see the docstring.
_SECOND_FAMILY = (
    "offsite_conversion.fb_pixel_custom",
    "offsite_conversion.fb_pixel_lead",
    "offsite_conversion.some_future_name",
)


def _actions(second: str) -> list[dict]:
    return [
        {"action_type": second, "value": "30"},
        {"action_type": "offsite_conversion.custom.123", "value": "30"},
        {"action_type": "link_click", "value": "80"},
    ]


def _insight(actions: list[dict], **extra) -> dict:
    return {"spend": "9.00", "impressions": 2000, "reach": 1500, "frequency": "1.3",
            "inline_link_clicks": 70, "cpm": "4.5", "ctr": "3.5",
            "campaign_name": "c", "actions": actions, **extra}


@pytest.mark.parametrize("second", _SECOND_FAMILY)
@pytest.mark.parametrize("goal", ["OFFSITE_CONVERSIONS", "LEAD_GENERATION", None])
def test_campaign_grain_counts_the_event_once(second: str, goal: str | None) -> None:
    row = _extract_perf(_insight(_actions(second)), artist_id=1, goal=goal)
    assert row["results"] == 30 == row["custom_conversions"], (
        f"results={row['results']} for one outbound event reported as {second} + "
        "offsite_conversion.custom.123 — the union of offsite families is back")
    assert row["cpr"] == round(9.0 / 30, 4)


class _FakeAccount:
    def __init__(self, insights: list[dict]) -> None:
        self._insights = insights
        self.fields: list[str] = []

    def get_insights(self, fields, params):
        self.fields = list(fields)
        return iter(self._insights)


def _ad_rows(insight: dict, goal: str):
    fetcher = _MetaInsightFetchMixin()
    fetcher.artist_id = 1
    fetcher.ad_account = _FakeAccount([insight])
    rows = fetcher._fetch_ad_insights("2026-09-01", "2026-09-01", {"ad1": goal})
    return fetcher.ad_account.fields, rows


@pytest.mark.parametrize("second", _SECOND_FAMILY)
def test_ad_grain_counts_the_event_once(second: str) -> None:
    ins = _insight(_actions(second), ad_id="ad1", date_start="2026-09-01", clicks=95)
    fields, rows = _ad_rows(ins, "OFFSITE_CONVERSIONS")
    (row,) = rows
    assert row["conversions"] == 30 == row["custom_conversions"], (
        f"ad-grain conversions={row['conversions']} — the union of offsite families is back")
    # The funnel stages the Créatives view draws (migration 138).
    assert "inline_link_clicks" in fields
    assert row["link_clicks"] == 70
    assert row["clicks"] == 95  # clicks (all) stays what it is, under its own name
    # The raw offsite names are kept, so the family rule stays auditable.
    assert row["offsite_actions"] == ";".join(sorted(
        [f"{second}=30", "offsite_conversion.custom.123=30"]))


def double_counts(results_for_goal) -> list[str]:
    """Second-family names under which `results_for_goal` counts the event more than once."""
    out = []
    for second in _SECOND_FAMILY:
        actions = {a["action_type"]: int(a["value"]) for a in _actions(second)}
        if results_for_goal(actions, "OFFSITE_CONVERSIONS") != 30:
            out.append(second)
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The two shapes the defect has actually had, fabricated here, must be seen."""
    def union(actions, goal):  # before 2026-09-26
        return sum(v for k, v in actions.items() if k.startswith("offsite_conversion"))

    def exact_custom(actions, goal):  # the 2026-05-28 regression, one family deep
        if "offsite_conversion.custom" in actions:
            return actions["offsite_conversion.custom"]
        return union(actions, goal)

    assert double_counts(union) == list(_SECOND_FAMILY)
    assert double_counts(exact_custom) == list(_SECOND_FAMILY)


def test_the_corrected_form_leaves_the_detector_silent() -> None:
    assert double_counts(_results_for_goal) == []


def test_the_id_suffixed_custom_name_is_still_matched() -> None:
    """The 2026-05-28 regression: an exact 'offsite_conversion.custom' match returned 0.

    Here it would miss the custom family and fall back to the pixel family.
    """
    actions = {"offsite_conversion.custom.987": 12, "offsite_conversion.fb_pixel_custom": 25}
    assert _results_for_goal(actions, "OFFSITE_CONVERSIONS") == 12


def test_a_pixel_only_conversion_still_has_a_result() -> None:
    """No custom family at all (7 day-rows of artist 1): the other offsite sum applies."""
    actions = {"offsite_conversion.fb_pixel_purchase": 4}
    assert _results_for_goal(actions, "OFFSITE_CONVERSIONS") == 4


# ── The DATA half: what the database says, once re-collected ──────────────────
#
# ⚠️ This guard sees ONLY rows written by the fixed collector. The pre-fix history
# (every row of artist 1 on 2026-09-26) is red by construction and stays so until the
# owner runs a full_history Meta re-collection — a production data rewrite this test
# must not pretend to have happened. The horizon is read, not typed: the first ad-grain
# row that carries `custom_conversions` (migration 138) was written by the fixed code,
# and the campaign grain is written in the same run. Sandbox tenants are excluded by
# `saas_artists.is_sandbox` — tenant 18 mirrors tenant 1 and would otherwise show a
# permanent, unreadable mixed verdict once only one of them is re-collected.
_HORIZON_SQL = """
    SELECT MIN(mi.collected_at) FROM meta_insights mi
      JOIN saas_artists sa ON sa.id = mi.artist_id AND NOT sa.is_sandbox
     WHERE mi.custom_conversions IS NOT NULL
"""
# `cpr IS NOT NULL` ⇔ a conversion goal (the collector suppresses CPR otherwise), so a
# THRUPLAY campaign whose results are video views is not mistaken for a double count.
_DOUBLE_COUNT_SQL = """
    SELECT d.artist_id, d.campaign_name, d.day_date, d.results, d.custom_conversions
      FROM meta_insights_performance_day d
      JOIN saas_artists sa ON sa.id = d.artist_id AND NOT sa.is_sandbox
     WHERE d.custom_conversions > 0 AND d.cpr IS NOT NULL
       AND d.results > 1.1 * d.custom_conversions
       AND d.collected_at >= %s
"""
_SEEN_SQL = """
    SELECT COUNT(*) FROM meta_insights_performance_day d
      JOIN saas_artists sa ON sa.id = d.artist_id AND NOT sa.is_sandbox
     WHERE d.custom_conversions > 0 AND d.cpr IS NOT NULL AND d.collected_at >= %s
"""
_AD_GRAIN_SQL = """
    SELECT mi.artist_id, mi.ad_id, mi.date, mi.conversions, mi.custom_conversions
      FROM meta_insights mi
      JOIN saas_artists sa ON sa.id = mi.artist_id AND NOT sa.is_sandbox
      JOIN meta_ads ma ON ma.ad_id = mi.ad_id AND ma.artist_id = mi.artist_id
      JOIN meta_adsets s ON s.adset_id = ma.adset_id AND s.artist_id = ma.artist_id
     WHERE mi.custom_conversions > 0
       AND s.optimization_goal IN ('OFFSITE_CONVERSIONS','LEAD_GENERATION','QUALITY_LEAD')
       AND mi.conversions <> mi.custom_conversions
"""


@requires_live_db()
def test_recollected_rows_count_the_event_once() -> None:
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        cols = db.fetch_query(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'meta_insights' AND column_name = 'custom_conversions'")
        if not cols:
            pytest.skip("migration 138 not applied — nothing re-collected to check")
        horizon = db.fetch_query(_HORIZON_SQL)[0][0]
        if horizon is None:
            pytest.skip("no Meta row written by the fixed collector yet "
                        "(owner: full_history re-collection pending)")
        seen = db.fetch_query(_SEEN_SQL, (horizon,))[0][0]
        if seen < 1:
            pytest.skip(f"no conversion-goal campaign-day collected since {horizon}")
        bad = db.fetch_query(_DOUBLE_COUNT_SQL, (horizon,))
        assert not bad, (f"{len(bad)}/{seen} campaign-days collected since {horizon} "
                         f"count one outbound event more than once, e.g. {bad[:3]}")
        bad_ads = db.fetch_query(_AD_GRAIN_SQL)
        assert not bad_ads, (f"{len(bad_ads)} ad-days whose result is not their outbound "
                             f"clicks under an offsite goal, e.g. {bad_ads[:3]}")
    finally:
        db.close()
