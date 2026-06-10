"""Meta Ads collector — config fetch mixin (campaigns/adsets/ads/creatives).

Type: Sub
Uses: facebook_business SDK (lazy, in-method), _meta_list
Depends on: _meta_retry, _meta_constants (leaf modules)

Mixed into MetaAdsApiCollector; methods cut verbatim from the original god-module.
"""
import json
import logging
from datetime import datetime, timezone

from ._meta_constants import _AD_STATUSES, _ADSET_STATUSES, _CAMPAIGN_STATUSES
from ._meta_retry import _meta_list, _meta_retry

logger = logging.getLogger(__name__)


class _MetaConfigFetchMixin:
    """Config-table fetch methods for MetaAdsApiCollector."""

    def _fetch_campaigns(self) -> list:
        from facebook_business.adobjects.campaign import Campaign
        try:
            fields = [
                Campaign.Field.id, Campaign.Field.name, Campaign.Field.status,
                Campaign.Field.objective, Campaign.Field.daily_budget,
                Campaign.Field.lifetime_budget, Campaign.Field.start_time,
                Campaign.Field.stop_time, Campaign.Field.created_time,
                Campaign.Field.updated_time,
            ]
            rows = []
            for c in _meta_list(
                self.ad_account.get_campaigns,
                fields=fields,
                params={'limit': 500, 'effective_status': _CAMPAIGN_STATUSES},
            ):
                rows.append({
                    'campaign_id':    c['id'],
                    'campaign_name':  c['name'],
                    'artist_id':      self.artist_id,
                    'status':         c.get('status'),
                    'objective':      c.get('objective'),
                    'daily_budget':   float(c['daily_budget']) / 100 if c.get('daily_budget') else None,
                    'lifetime_budget': float(c['lifetime_budget']) / 100 if c.get('lifetime_budget') else None,
                    'start_time':     c.get('start_time'),
                    'end_time':       c.get('stop_time'),
                    'created_time':   c.get('created_time'),
                    'updated_time':   c.get('updated_time'),
                    'collected_at':   datetime.now(timezone.utc),
                })
            logger.info(f"  {len(rows)} campaigns")
            return rows
        except Exception:
            logger.exception("_fetch_campaigns failed")
            raise

    def _fetch_adsets(self, valid_campaign_ids: set) -> list:
        from facebook_business.adobjects.adset import AdSet
        try:
            fields = [
                AdSet.Field.id, AdSet.Field.name, AdSet.Field.campaign_id,
                AdSet.Field.status, AdSet.Field.optimization_goal,
                AdSet.Field.billing_event, AdSet.Field.daily_budget,
                AdSet.Field.lifetime_budget, AdSet.Field.start_time,
                AdSet.Field.end_time, AdSet.Field.targeting,
            ]
            rows, orphans = [], 0
            for a in _meta_list(
                self.ad_account.get_ad_sets,
                fields=fields,
                params={'limit': 500, 'effective_status': _ADSET_STATUSES},
            ):
                if a['campaign_id'] not in valid_campaign_ids:
                    orphans += 1
                    continue

                # Parse targeting JSON into discrete columns (matches CSV schema)
                tgt = a.get('targeting')
                tgt_dict = tgt.export_all_data() if hasattr(tgt, 'export_all_data') else (tgt or {})
                tgt_json = json.dumps(tgt_dict)

                geo = tgt_dict.get('geo_locations', {})
                rows.append({
                    'adset_id':            a['id'],
                    'adset_name':          a['name'],
                    'artist_id':           self.artist_id,
                    'campaign_id':         a['campaign_id'],
                    'status':              a.get('status'),
                    'optimization_goal':   a.get('optimization_goal'),
                    'billing_event':       a.get('billing_event'),
                    'daily_budget':        float(a['daily_budget']) / 100 if a.get('daily_budget') else None,
                    'lifetime_budget':     float(a['lifetime_budget']) / 100 if a.get('lifetime_budget') else None,
                    'start_time':          a.get('start_time'),
                    'end_time':            a.get('end_time'),
                    'targeting':           tgt_json,
                    # Decomposed columns (CSV-compatible)
                    'countries':           ','.join(geo.get('countries', [])),
                    'cities':              ','.join(
                        c.get('name', '') for c in geo.get('cities', [])
                    ),
                    'gender':              ','.join(str(g) for g in tgt_dict.get('genders', [])),
                    'age_min':             str(tgt_dict.get('age_min', '')),
                    'age_max':             str(tgt_dict.get('age_max', '')),
                    'flexible_inclusions': json.dumps(tgt_dict.get('flexible_spec', [])),
                    'advantage_audience':  str(
                        tgt_dict.get('targeting_automation', {}).get('advantage_audience', '')
                    ),
                    'publisher_platforms': ','.join(tgt_dict.get('publisher_platforms', [])),
                    'instagram_positions': ','.join(tgt_dict.get('instagram_positions', [])),
                    'device_platforms':    ','.join(tgt_dict.get('device_platforms', [])),
                    'collected_at':        datetime.now(timezone.utc),
                })
            logger.info(f"  {len(rows)} adsets, {orphans} orphans skipped")
            return rows
        except Exception:
            logger.exception("_fetch_adsets failed")
            raise

    def _fetch_ads(self, valid_adset_ids: set) -> list:
        from facebook_business.adobjects.ad import Ad
        try:
            fields = [
                Ad.Field.id, Ad.Field.name, Ad.Field.adset_id,
                Ad.Field.campaign_id, Ad.Field.status, Ad.Field.creative,
                Ad.Field.created_time, Ad.Field.updated_time,
            ]
            rows, orphans = [], 0
            for a in _meta_list(
                self.ad_account.get_ads,
                fields=fields,
                params={'limit': 500, 'effective_status': _AD_STATUSES},
            ):
                if a['adset_id'] not in valid_adset_ids:
                    orphans += 1
                    continue
                rows.append({
                    'ad_id':        a['id'],
                    'ad_name':      a['name'],
                    'artist_id':    self.artist_id,
                    'adset_id':     a['adset_id'],
                    'campaign_id':  a['campaign_id'],
                    'status':       a.get('status'),
                    'creative_id':  (a.get('creative') or {}).get('id'),
                    'created_time': a.get('created_time'),
                    'updated_time': a.get('updated_time'),
                    'collected_at': datetime.now(timezone.utc),
                })
            logger.info(f"  {len(rows)} ads, {orphans} orphans skipped")
            return rows
        except Exception:
            logger.exception("_fetch_ads failed")
            raise

    # ── Fetch: creatives ──────────────────────────────────────────────────────

    def _fetch_creatives(self, ads: list) -> list:
        """Fetch creative content (title, body, CTA) for each ad.

        Returns list of dicts keyed by ad_id, ready to upsert into meta_ads.
        """
        try:
            creative_ids = list({
                a['creative_id'] for a in ads if a.get('creative_id')
            })
            if not creative_ids:
                logger.info("  0 creatives (no creative_id on ads)")
                return []

            from facebook_business.adobjects.adcreative import AdCreative

            fields = [
                AdCreative.Field.id,
                AdCreative.Field.title,
                AdCreative.Field.body,
                AdCreative.Field.call_to_action_type,
                AdCreative.Field.thumbnail_url,
            ]

            # Build creative_id → content map
            creative_map = {}
            for cid in creative_ids:
                try:
                    cr = _meta_retry(AdCreative(cid).api_get, fields=fields)
                    creative_map[cid] = {
                        'title':          cr.get('title'),
                        'body':           cr.get('body'),
                        'call_to_action': cr.get('call_to_action_type'),
                    }
                except Exception as e:
                    logger.warning(f"  creative {cid} fetch failed: {e}")
                    # Non-fatal: some creatives may be inaccessible; continue

            # Build ad-level rows (upsert creative fields onto meta_ads)
            rows = []
            for a in ads:
                cid = a.get('creative_id')
                cr = creative_map.get(cid, {}) if cid else {}
                rows.append({
                    'ad_id':          a['ad_id'],
                    'title':          cr.get('title'),
                    'body':           cr.get('body'),
                    'call_to_action': cr.get('call_to_action'),
                })

            logger.info(
                f"  {len(creative_map)}/{len(creative_ids)} creatives fetched, "
                f"{len(rows)} ad rows enriched"
            )
            return rows
        except Exception:
            logger.exception("_fetch_creatives failed")
            raise
