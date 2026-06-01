"""Unit tests — MetaAdsApiCollector._extract_perf / _extract_eng.

Covers:
- custom_conversions counts only offsite_conversion.custom (not link_click)
- results == custom_conversions (no double-counting)
- lp_views extracted correctly from landing_page_view action type
- CPR = spend / custom_conversions (None when 0 conversions)
- CPC = spend / link_clicks (None when 0 clicks)
- zero-action edge case
- mixed action types — only relevant ones counted
"""
import pytest
from src.collectors.meta_ads_api_collector import _extract_perf, _extract_eng


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insight(spend="10.00", impressions=1000, reach=900, frequency="1.1",
             inline_link_clicks=50, cpm="10.0", ctr="5.0", actions=None):
    """Build a minimal insight dict as returned by the Meta API."""
    return {
        "spend": spend,
        "impressions": impressions,
        "reach": reach,
        "frequency": frequency,
        "inline_link_clicks": inline_link_clicks,
        "cpm": cpm,
        "ctr": ctr,
        "campaign_name": "Test Campaign",
        "actions": actions or [],
    }


# ---------------------------------------------------------------------------
# _extract_perf — custom_conversions / results
# ---------------------------------------------------------------------------

class TestExtractPerfCustomConversions:

    def test_no_actions_gives_zero_conversions(self):
        row = _extract_perf(_insight(actions=[]), artist_id=1)
        assert row["custom_conversions"] == 0
        assert row["results"] == 0
        assert row["cpr"] is None

    def test_link_click_not_counted_in_custom_conversions(self):
        """link_click must NOT inflate custom_conversions (regression guard)."""
        actions = [{"action_type": "link_click", "value": "30"}]
        row = _extract_perf(_insight(actions=actions), artist_id=1)
        assert row["custom_conversions"] == 0
        assert row["results"] == 0

    def test_offsite_conversion_counted(self):
        actions = [{"action_type": "offsite_conversion.custom", "value": "15"}]
        row = _extract_perf(_insight(actions=actions), artist_id=1)
        assert row["custom_conversions"] == 15
        assert row["results"] == 15

    def test_results_equals_custom_conversions(self):
        """results is an alias for custom_conversions — no double-counting."""
        actions = [
            {"action_type": "link_click",               "value": "50"},
            {"action_type": "offsite_conversion.custom", "value": "20"},
            {"action_type": "landing_page_view",         "value": "40"},
        ]
        row = _extract_perf(_insight(actions=actions), artist_id=1)
        assert row["custom_conversions"] == 20
        assert row["results"] == row["custom_conversions"]

    def test_cpr_computed_from_custom_conversions(self):
        actions = [{"action_type": "offsite_conversion.custom", "value": "5"}]
        row = _extract_perf(_insight(spend="10.00", actions=actions), artist_id=1)
        assert row["cpr"] == round(10.0 / 5, 4)

    def test_cpr_none_when_no_conversions(self):
        row = _extract_perf(_insight(spend="10.00", actions=[]), artist_id=1)
        assert row["cpr"] is None

    def test_cpr_none_when_only_link_clicks(self):
        """Before fix: link_click inflated results → CPR was computed. Now None."""
        actions = [{"action_type": "link_click", "value": "50"}]
        row = _extract_perf(_insight(spend="10.00", actions=actions), artist_id=1)
        assert row["cpr"] is None

    def test_lp_views_extracted(self):
        actions = [
            {"action_type": "landing_page_view",         "value": "35"},
            {"action_type": "offsite_conversion.custom", "value": "10"},
        ]
        row = _extract_perf(_insight(actions=actions), artist_id=1)
        assert row["lp_views"] == 35

    def test_lp_views_zero_when_absent(self):
        row = _extract_perf(_insight(actions=[]), artist_id=1)
        assert row["lp_views"] == 0

    def test_cpc_from_inline_link_clicks(self):
        row = _extract_perf(_insight(spend="10.00", inline_link_clicks=25), artist_id=1)
        assert row["cpc"] == round(10.0 / 25, 4)

    def test_cpc_none_when_zero_clicks(self):
        row = _extract_perf(_insight(spend="10.00", inline_link_clicks=0), artist_id=1)
        assert row["cpc"] is None

    def test_artist_id_propagated(self):
        row = _extract_perf(_insight(), artist_id=42)
        assert row["artist_id"] == 42

    def test_multiple_conversion_events_summed(self):
        """Two offsite_conversion.custom actions (e.g., two breakdowns) sum correctly."""
        actions = [
            {"action_type": "offsite_conversion.custom", "value": "8"},
            {"action_type": "offsite_conversion.custom", "value": "4"},
        ]
        row = _extract_perf(_insight(actions=actions), artist_id=1)
        assert row["custom_conversions"] == 12

    def test_unknown_action_type_ignored(self):
        actions = [{"action_type": "video_view", "value": "100"}]
        row = _extract_perf(_insight(actions=actions), artist_id=1)
        assert row["custom_conversions"] == 0
        assert row["lp_views"] == 0


# ---------------------------------------------------------------------------
# _extract_eng — engagement mapping unchanged
# ---------------------------------------------------------------------------

class TestExtractEng:

    def test_empty_actions_all_zeros(self):
        row = _extract_eng(_insight(actions=[]), artist_id=1)
        for col in ["page_interactions", "post_reactions", "comments",
                    "saves", "shares", "link_clicks", "post_likes"]:
            assert row[col] == 0

    def test_engagement_fields_mapped(self):
        actions = [
            {"action_type": "post_reaction",              "value": "5"},
            {"action_type": "comment",                    "value": "3"},
            {"action_type": "onsite_conversion.post_save","value": "7"},
            {"action_type": "link_click",                 "value": "20"},
        ]
        row = _extract_eng(_insight(actions=actions), artist_id=1)
        assert row["post_reactions"] == 5
        assert row["comments"]       == 3
        assert row["saves"]          == 7
        assert row["link_clicks"]    == 20


# ---------------------------------------------------------------------------
# _extract_perf — results driven by campaign objective (Meta's native "Results")
# ---------------------------------------------------------------------------

class TestExtractPerfGoal:
    """results must match the AD SET optimization_goal, not always custom conversions.

    Regression guard for the engagement-campaign bug: results was hardcoded to
    offsite_conversion.custom, which (a) returned 0 for engagement/traffic goals and
    (b) missed the id-suffixed action_type Meta actually returns
    ('offsite_conversion.custom.<id>'). CPR is shown only for conversion goals.
    """

    _ACTIONS = [
        {"action_type": "post_engagement",               "value": "1887"},
        {"action_type": "link_click",                    "value": "80"},
        {"action_type": "offsite_conversion.custom.123", "value": "12"},
    ]

    def test_post_engagement_goal(self):
        row = _extract_perf(_insight(spend="20.00", actions=self._ACTIONS),
                            artist_id=1, goal="POST_ENGAGEMENT")
        assert row["results"] == 1887
        assert row["cpr"] is None  # engagement goal → CPR suppressed

    def test_link_clicks_goal(self):
        row = _extract_perf(_insight(actions=self._ACTIONS), artist_id=1,
                            goal="LINK_CLICKS")
        assert row["results"] == 80
        assert row["cpr"] is None  # traffic goal → CPR suppressed

    def test_offsite_conversions_goal_prefix_match(self):
        """The id-suffixed action_type must be counted (core of the bug)."""
        row = _extract_perf(_insight(spend="24.00", actions=self._ACTIONS),
                            artist_id=1, goal="OFFSITE_CONVERSIONS")
        assert row["results"] == 12
        assert row["cpr"] == round(24.0 / 12, 4)  # conversion goal → CPR shown

    def test_custom_conversions_prefix_match(self):
        actions = [{"action_type": "offsite_conversion.custom.999", "value": "7"}]
        row = _extract_perf(_insight(actions=actions), artist_id=1,
                            goal="OFFSITE_CONVERSIONS")
        assert row["custom_conversions"] == 7  # prefix match catches the id suffix

    def test_reach_goal_has_no_action_result(self):
        row = _extract_perf(_insight(actions=self._ACTIONS), artist_id=1, goal="REACH")
        assert row["results"] == 0
        assert row["cpr"] is None

    def test_unknown_goal_falls_back_to_offsite_conversions(self):
        actions = [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "4"}]
        row = _extract_perf(_insight(spend="8.00", actions=actions),
                            artist_id=1, goal=None)
        assert row["results"] == 4
        assert row["cpr"] == round(8.0 / 4, 4)  # unknown goal → conversion intent → CPR shown


# ---------------------------------------------------------------------------
# Per-chunk persistence (a late throttle must not discard earlier insights)
# ---------------------------------------------------------------------------

class _FakeDB:
    """Records upserts / deletes without touching a real Postgres."""

    def __init__(self):
        self.upserts = []   # [(table, rows)]
        self.deletes = []   # [(query, params)]

    def upsert_many(self, table, data, conflict_columns=None, update_columns=None):
        self.upserts.append((table, [dict(r) for r in data]))
        return len(data)

    def execute_query(self, query, params=None):
        self.deletes.append((query, params))

    def fetch_query(self, query, params=None):
        return []


def _bare_collector(db):
    """Build a collector without running __init__ (no Meta creds / API needed)."""
    from src.collectors.meta_ads_api_collector import MetaAdsApiCollector
    c = MetaAdsApiCollector.__new__(MetaAdsApiCollector)
    c.artist_id = 1
    c.db = db
    return c


class TestPersistInsights:

    def test_trims_unknown_columns_and_skips_empty(self):
        db = _FakeDB()
        c = _bare_collector(db)
        c._persist_insights({
            'meta_insights_performance_day': [{
                'artist_id': 1, 'campaign_name': 'C', 'day_date': '2026-01-01',
                'spend': 1.0, 'impressions': 10, 'reach': 8, 'results': 2,
                'custom_conversions': 2, 'cpr': 0.5, 'collected_at': 'ts',
                '_date': 'LEAK', 'frequency': 'LEAK',   # not in the table's column set
            }],
            'meta_insights_performance_age': [],          # empty → skipped
        })
        assert len(db.upserts) == 1                       # empty table not upserted
        table, rows = db.upserts[0]
        assert table == 'meta_insights_performance_day'
        assert '_date' not in rows[0] and 'frequency' not in rows[0]
        assert rows[0]['campaign_name'] == 'C'

    def test_late_throttle_keeps_earlier_chunk(self):
        from datetime import date, timedelta
        db = _FakeDB()
        c = _bare_collector(db)
        c._build_goal_maps = lambda *a, **k: ({}, {}, {})
        c._fetch_ad_insights = lambda *a, **k: []

        calls = {'n': 0}

        def fake_call_insights(since, until, breakdown=None, time_increment=None,
                               goal_by_campaign=None):
            calls['n'] += 1
            if calls['n'] == 1:                           # first monthly chunk OK
                return ([{'_date': since, 'artist_id': 1, 'campaign_name': 'C',
                          'spend': 1.0, 'impressions': 10, 'reach': 8, 'results': 2,
                          'custom_conversions': 2, 'cpr': 0.5}], [])
            raise RuntimeError("Meta throttle (simulated) on chunk 2")

        c._call_insights = fake_call_insights

        # start_time ~70 days ago → at least two monthly chunks
        start = (date.today().replace(day=1) - timedelta(days=70)).isoformat()
        campaigns = [{'campaign_id': '1', 'campaign_name': 'C', 'start_time': start}]

        with pytest.raises(RuntimeError):
            c._fetch_all_insights(campaigns, full_history=True,
                                  persist_cb=c._persist_insights)

        # The first chunk was persisted BEFORE the throttle aborted the run.
        persisted = {t for t, _ in db.upserts}
        assert 'meta_insights_performance' in persisted
        assert 'meta_insights_performance_day' in persisted


class TestPruneRenamedCampaigns:

    def test_empty_campaigns_is_noop(self):
        db = _FakeDB()
        _bare_collector(db)._prune_renamed_campaigns([])
        assert db.deletes == []

    def test_deletes_stale_names_across_campaign_grain_tables(self):
        from src.collectors.meta_ads_api_collector import _CAMPAIGN_GRAIN_TABLES
        db = _FakeDB()
        c = _bare_collector(db)
        c._prune_renamed_campaigns([
            {'campaign_name': 'C2'}, {'campaign_name': 'C1'}, {'campaign_name': None},
        ])
        assert len(db.deletes) == len(_CAMPAIGN_GRAIN_TABLES)
        for query, params in db.deletes:
            assert 'DELETE FROM' in query and 'campaign_name <> ALL' in query
            assert params == (1, ['C1', 'C2'])           # sorted, NULL dropped, scoped by artist_id
