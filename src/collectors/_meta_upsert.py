"""Meta Ads collector — upsert mixin (config + insight persistence).

Type: Sub
Uses: PostgresHandler (via self.db), validate_table (lazy, in-method)
Depends on: _meta_constants (leaf module)

Mixed into MetaAdsApiCollector; methods cut verbatim from the original god-module.
"""
import logging

from ._meta_constants import _CAMPAIGN_GRAIN_TABLES

logger = logging.getLogger(__name__)


class _MetaUpsertMixin:
    """Persistence methods for MetaAdsApiCollector."""

    def _upsert_config(self, campaigns: list, adsets: list, ads: list, creatives: list):
        """Upsert the 4 config tables (campaigns/adsets/ads + creative enrichment).

        Called before the insight fetch so a later throttle cannot discard config work.
        """
        try:
            if campaigns:
                self.db.upsert_many(
                    'meta_campaigns', campaigns,
                    conflict_columns=['campaign_id'],
                    update_columns=[
                        'campaign_name', 'artist_id', 'status', 'objective',
                        'daily_budget', 'lifetime_budget', 'start_time',
                        'end_time', 'created_time', 'updated_time',
                    ],
                )

            if adsets:
                self.db.upsert_many(
                    'meta_adsets', adsets,
                    conflict_columns=['adset_id'],
                    update_columns=[
                        'adset_name', 'artist_id', 'campaign_id', 'status',
                        'optimization_goal', 'billing_event', 'daily_budget',
                        'lifetime_budget', 'start_time', 'end_time', 'targeting',
                        'countries', 'cities', 'gender', 'age_min', 'age_max',
                        'flexible_inclusions', 'advantage_audience',
                        'publisher_platforms', 'instagram_positions', 'device_platforms',
                    ],
                )

            if ads:
                self.db.upsert_many(
                    'meta_ads', ads,
                    conflict_columns=['ad_id'],
                    update_columns=[
                        'ad_name', 'artist_id', 'adset_id', 'campaign_id',
                        'status', 'creative_id', 'created_time', 'updated_time',
                    ],
                )

            # Enrich meta_ads with creative content (separate upsert, subset of columns)
            if creatives:
                for cr in creatives:
                    self.db.execute_query(
                        """
                        UPDATE meta_ads
                        SET title          = %(title)s,
                            body           = %(body)s,
                            call_to_action = %(call_to_action)s
                        WHERE ad_id = %(ad_id)s
                          AND (%(title)s IS NOT NULL OR %(body)s IS NOT NULL)
                        """,
                        cr,
                    )
        except Exception:
            logger.exception("_upsert_config failed")
            raise

    def _prune_renamed_campaigns(self, campaigns: list):
        """Delete campaign-grain insight rows whose campaign_name no longer exists.

        Campaign-grain tables key by campaign_name, so a campaign RENAME orphans stale
        rows under the old name (ad/adset grains key by id and are immune). Guarded: an
        empty campaign list (failed/partial fetch) is a no-op — never a mass delete.
        """
        from src.database.postgres_handler import validate_table
        names = sorted({c['campaign_name'] for c in campaigns if c.get('campaign_name')})
        if not names:
            return
        try:
            for tbl in _CAMPAIGN_GRAIN_TABLES:
                validate_table(tbl)
                self.db.execute_query(
                    f"DELETE FROM {tbl} WHERE artist_id = %s AND campaign_name <> ALL(%s)",
                    (self.artist_id, names),
                )
            logger.info(
                f"  campaign-name prune ran across {len(_CAMPAIGN_GRAIN_TABLES)} "
                f"campaign-grain tables ({len(names)} current campaigns)"
            )
        except Exception:
            logger.exception("_prune_renamed_campaigns failed")
            raise

    @staticmethod
    def _insight_upsert_maps() -> tuple:
        """Return (insight_cols, conflict_cols) for every insight table.

        Single source of truth for the upsert column/key config, shared by the
        per-chunk persistence path (_persist_insights).
        """
        # Columns allowed in each insight table (INSERT uses only these keys)
        _insight_cols = {
                'meta_insights_performance': [
                    'spend', 'impressions', 'reach', 'frequency', 'results',
                    'custom_conversions', 'cpr', 'cpm', 'link_clicks', 'cpc', 'ctr', 'lp_views',
                ],
                'meta_insights_performance_day': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                    'collected_at',
                ],
                'meta_insights_performance_age': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                ],
                'meta_insights_performance_country': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                ],
                'meta_insights_performance_placement': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
                ],
                'meta_insights_engagement': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_day': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_age': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_country': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights_engagement_placement': [
                    'page_interactions', 'post_reactions', 'comments',
                    'saves', 'shares', 'link_clicks', 'post_likes',
                ],
                'meta_insights': [
                    'impressions', 'clicks', 'spend', 'reach', 'frequency',
                    'cpc', 'cpm', 'ctr', 'conversions', 'cost_per_conversion',
                ],
            }

        _conflict_cols = {
            'meta_insights_performance':           ['artist_id', 'campaign_name', 'date_start'],
            'meta_insights_performance_day':       ['artist_id', 'campaign_name', 'day_date'],
            'meta_insights_performance_age':       ['artist_id', 'campaign_name', 'age_range'],
            'meta_insights_performance_country':   ['artist_id', 'campaign_name', 'country'],
            'meta_insights_performance_placement': ['artist_id', 'campaign_name', 'platform', 'placement'],
            'meta_insights_engagement':            ['artist_id', 'campaign_name', 'date_start'],
            'meta_insights_engagement_day':        ['artist_id', 'campaign_name', 'day_date'],
            'meta_insights_engagement_age':        ['artist_id', 'campaign_name', 'age_range'],
            'meta_insights_engagement_country':    ['artist_id', 'campaign_name', 'country'],
            'meta_insights_engagement_placement':  ['artist_id', 'campaign_name', 'platform', 'placement'],
            'meta_insights':                       ['artist_id', 'ad_id', 'date'],
        }

        # Ad/adset-level breakdown tables share column sets — generate their 12 entries.
        _perf_bd_cols = ['spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr']
        _eng_bd_cols = ['page_interactions', 'post_reactions', 'comments',
                        'saves', 'shares', 'link_clicks', 'post_likes']
        _bd_dim_keys = {'country': ['country'],
                        'placement': ['platform', 'placement'],
                        'age': ['age_range']}
        for _lvl, _idf in (('ad', 'ad_id'), ('adset', 'adset_id')):
            for _dim, _dimcols in _bd_dim_keys.items():
                _key = ['artist_id', _idf, *_dimcols]
                _insight_cols[f'meta_insights_performance_{_lvl}_{_dim}'] = _perf_bd_cols
                _insight_cols[f'meta_insights_engagement_{_lvl}_{_dim}'] = _eng_bd_cols
                _conflict_cols[f'meta_insights_performance_{_lvl}_{_dim}'] = _key
                _conflict_cols[f'meta_insights_engagement_{_lvl}_{_dim}'] = _key

        return _insight_cols, _conflict_cols

    def _persist_insights(self, insights: dict):
        """Upsert a subset of insight tables (per-chunk durability).

        Called after each fetched chunk/breakdown so a later throttle never discards
        already-fetched insights — replaces the old all-or-nothing end-of-run upsert.
        """
        try:
            insight_cols, conflict_cols = self._insight_upsert_maps()
            for tbl, rows in insights.items():
                if not rows:
                    continue
                allowed = set(conflict_cols[tbl]) | set(insight_cols[tbl])
                trimmed = [{k: v for k, v in r.items() if k in allowed} for r in rows]
                self.db.upsert_many(
                    tbl, trimmed,
                    conflict_columns=conflict_cols[tbl],
                    update_columns=insight_cols[tbl],
                )
        except Exception:
            logger.exception("_persist_insights failed")
            raise
