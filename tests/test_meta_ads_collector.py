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
