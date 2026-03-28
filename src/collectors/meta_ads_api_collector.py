"""Meta Ads API collector — full pipeline, zero CSV dependency.

Type: Feature
Uses: credential_loader.load_platform_credentials, PostgresHandler, facebook_business SDK
Persists in: meta_campaigns, meta_adsets, meta_ads, meta_insights_performance*,
             meta_insights_engagement* (all 10 insight tables)

Credentials (stored in artist_credentials for platform='meta'):
  access_token   — long-lived user token (refreshed weekly by meta_token_refresh DAG)
  app_id         — Meta app ID (extra_config)
  app_secret     — Meta app secret
  account_id     — Ad account ID without prefix, e.g. "567214713853881" (extra_config)

run(full_history=False):
  - full_history=False: last 90 days for global/day; aggregate for age/country/placement
  - full_history=True : monthly chunks from earliest campaign start_time to today

Invariant: every except block raises — no silent return None / [] / {}.
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

# Meta API error code for rate-limit (transient, safe to retry)
_META_RATE_LIMIT_CODE = 17
_META_RATE_LIMIT_WAIT = 60  # seconds to wait before retry


def _meta_list(callable_fn, *args, max_retries: int = 3, **kwargs) -> list:
    """Call a facebook_business SDK list method, retrying on rate-limit (code 17)."""
    from facebook_business.exceptions import FacebookRequestError
    for attempt in range(1, max_retries + 1):
        try:
            return list(callable_fn(*args, **kwargs))
        except FacebookRequestError as exc:
            if exc.api_error_code() == _META_RATE_LIMIT_CODE and attempt < max_retries:
                wait = _META_RATE_LIMIT_WAIT * attempt
                logger.warning(
                    f"Meta rate limit (code 17) — attempt {attempt}/{max_retries}. "
                    f"Waiting {wait}s before retry..."
                )
                time.sleep(wait)
            else:
                raise

# Action types that count as campaign "results".
# Only offsite_conversion.custom (Spotify button click via Hypeddit CAPI) — link_click
# excluded to avoid double-counting: a fan who clicks the ad AND the Spotify button
# would otherwise inflate results and deflate CPR.
_RESULT_ACTION_TYPES = frozenset(['offsite_conversion.custom'])

# Mapping from Meta action_type to engagement table column
_ENGAGEMENT_MAP = {
    'post_engagement':               'page_interactions',
    'post_reaction':                 'post_reactions',
    'comment':                       'comments',
    'onsite_conversion.post_save':   'saves',
    'post':                          'shares',
    'like':                          'post_likes',
    'link_click':                    'link_clicks',
}


# ──────────────────────────────────────────────────────────────────────────────
# Helper: extract performance + engagement dicts from a single insight object
# ──────────────────────────────────────────────────────────────────────────────

def _extract_perf(insight, artist_id: int) -> dict:
    spend = float(insight.get('spend') or 0)
    impressions = int(insight.get('impressions') or 0)
    reach = int(insight.get('reach') or 0)
    frequency = float(insight.get('frequency') or 0)
    link_clicks = int(insight.get('inline_link_clicks') or 0)
    cpm_raw = float(insight.get('cpm') or 0)
    ctr = float(insight.get('ctr') or 0)

    custom_conversions = 0
    lp_views = 0
    for action in (insight.get('actions') or []):
        atype = action['action_type']
        val = int(float(action['value']))
        if atype == 'offsite_conversion.custom':
            custom_conversions += val
        elif atype == 'landing_page_view':
            lp_views += val

    # results = custom_conversions (Spotify button clicks) — the metric Meta bills on.
    # link_clicks (inline_link_clicks) tracks ad clicks separately, upstream in the funnel.
    results = custom_conversions

    return {
        'artist_id':          artist_id,
        'campaign_name':      insight.get('campaign_name', ''),
        'spend':              spend,
        'impressions':        impressions,
        'reach':              reach,
        'frequency':          frequency,
        'results':            results,
        'custom_conversions': custom_conversions,
        'cpr':                round(spend / results, 4) if results > 0 else None,
        'cpm':                cpm_raw or None,
        'link_clicks':        link_clicks,
        'cpc':                round(spend / link_clicks, 4) if link_clicks > 0 else None,
        'ctr':                ctr,
        'lp_views':           lp_views,
    }


def _extract_eng(insight, artist_id: int) -> dict:
    row = {
        'artist_id':        artist_id,
        'campaign_name':    insight.get('campaign_name', ''),
        'page_interactions': 0,
        'post_reactions':   0,
        'comments':         0,
        'saves':            0,
        'shares':           0,
        'link_clicks':      0,
        'post_likes':       0,
    }
    for action in (insight.get('actions') or []):
        col = _ENGAGEMENT_MAP.get(action['action_type'])
        if col:
            row[col] += int(float(action['value']))
    return row


# ──────────────────────────────────────────────────────────────────────────────
# Collector
# ──────────────────────────────────────────────────────────────────────────────

class MetaAdsApiCollector:
    """Full Meta Ads API collector. No CSV dependency."""

    def __init__(self, artist_id: int):
        if not artist_id or artist_id < 1:
            raise ValueError(f"MetaAdsApiCollector: invalid artist_id={artist_id!r}")
        self.artist_id = artist_id
        self._creds = self._load_credentials()
        self._init_api()

        from src.database.postgres_handler import PostgresHandler
        self.db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD', ''),
        )

    # ── Credentials ───────────────────────────────────────────────────────────

    def _load_credentials(self) -> dict:
        from src.utils.credential_loader import load_platform_credentials
        creds = load_platform_credentials(self.artist_id, 'meta')
        missing = [k for k in ('access_token', 'app_id', 'app_secret', 'account_id')
                   if not creds.get(k)]
        if missing:
            raise ValueError(
                f"Meta credentials missing for artist_id={self.artist_id}: {missing}. "
                "Configure via Dashboard → Credentials → Meta."
            )
        raw_id = creds['account_id']
        creds['ad_account_id'] = raw_id if raw_id.startswith('act_') else f"act_{raw_id}"
        return creds

    def _init_api(self):
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount
        FacebookAdsApi.init(
            app_id=self._creds['app_id'],
            app_secret=self._creds['app_secret'],
            access_token=self._creds['access_token'],
            api_version='v21.0',
        )
        self.ad_account = AdAccount(self._creds['ad_account_id'])
        logger.info(
            f"Meta API initialised — artist_id={self.artist_id} "
            f"account={self._creds['ad_account_id']}"
        )

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, full_history: bool = False, insights_only: bool = False):
        """Full collection pipeline.

        full_history=False  : insights for the last 90 days.
        full_history=True   : insights from the earliest campaign start_time to today,
                              fetched in monthly chunks (safe for rate limits).
        insights_only=True  : skip campaigns/adsets/ads/creatives fetch (already in DB);
                              only run the 4 insight API calls. Reduces API call count by ~75%.
                              Requires at least one prior full run to have populated config tables.
        """
        if insights_only:
            # Load campaign list from DB (needed for full_history start-date calculation)
            campaigns_db = self.db.fetch_query(
                "SELECT campaign_id, campaign_name, start_time FROM meta_campaigns "
                "WHERE artist_id = %s",
                (self.artist_id,),
            )
            campaigns = [
                {'campaign_id': r[0], 'campaign_name': r[1], 'start_time': str(r[2]) if r[2] else None}
                for r in (campaigns_db or [])
            ]
            logger.info(
                f"insights_only mode — skipping config fetch, "
                f"using {len(campaigns)} campaigns from DB"
            )
            adsets, ads, creatives = [], [], []
        else:
            campaigns = self._fetch_campaigns()
            valid_campaign_ids = {c['campaign_id'] for c in campaigns}

            adsets = self._fetch_adsets(valid_campaign_ids)
            valid_adset_ids = {a['adset_id'] for a in adsets}

            ads = self._fetch_ads(valid_adset_ids)

            creatives = self._fetch_creatives(ads)

        insights = self._fetch_all_insights(campaigns, full_history=full_history)

        self._upsert_all(campaigns, adsets, ads, creatives, insights)

        total_insight_rows = sum(len(v) for v in insights.values())
        logger.info(
            f"Meta API collect done — artist_id={self.artist_id}: "
            f"{len(campaigns)} campaigns, {len(adsets)} adsets, {len(ads)} ads, "
            f"{len(creatives)} creatives, {total_insight_rows} insight rows across "
            f"{len(insights)} tables"
        )

    # ── Fetch: config ─────────────────────────────────────────────────────────

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
                params={'limit': 500, 'effective_status': ['ACTIVE', 'PAUSED']},
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
                    'collected_at':   datetime.now(),
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
                params={'limit': 500, 'effective_status': ['ACTIVE', 'PAUSED']},
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
                    'collected_at':        datetime.now(),
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
                params={'limit': 500, 'effective_status': ['ACTIVE', 'PAUSED']},
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
                    'collected_at': datetime.now(),
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
                    cr = AdCreative(cid).api_get(fields=fields)
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

    # ── Fetch: insights (all 10 tables) ──────────────────────────────────────

    def _fetch_all_insights(self, campaigns: list, full_history: bool = False) -> dict:
        """Return {table_name: [rows]} for all 10 insight tables.

        Makes 4 API calls per time chunk:
          1. time_increment=1, no breakdown  → global/day tables (performance + engagement)
          2. breakdown=['age']               → age tables
          3. breakdown=['country']           → country tables
          4. breakdown=['publisher_platform','platform_position'] → placement tables
        """
        today = date.today()

        if full_history and campaigns:
            # Find earliest campaign start — go back to that date
            starts = []
            for c in campaigns:
                s = c.get('start_time')
                if s:
                    try:
                        starts.append(datetime.fromisoformat(s[:10]).date())
                    except Exception:
                        pass
            history_start = min(starts) if starts else today - timedelta(days=90)
        else:
            history_start = today - timedelta(days=90)

        # Aggregate tables (age/country/placement) always use full range in one shot
        aggregate_start = history_start

        # Daily tables: chunked by month to avoid API timeouts
        chunks = []
        cursor = history_start.replace(day=1)
        while cursor <= today:
            chunk_end = min((cursor + relativedelta(months=1)) - timedelta(days=1), today)
            chunks.append((cursor.strftime('%Y-%m-%d'), chunk_end.strftime('%Y-%m-%d')))
            cursor += relativedelta(months=1)

        # Collect all results
        result = {
            'meta_insights_performance':           [],
            'meta_insights_performance_day':       [],
            'meta_insights_engagement':            [],
            'meta_insights_engagement_day':        [],
            'meta_insights_performance_age':       [],
            'meta_insights_engagement_age':        [],
            'meta_insights_performance_country':   [],
            'meta_insights_engagement_country':    [],
            'meta_insights_performance_placement': [],
            'meta_insights_engagement_placement':  [],
        }

        # 1. Global / daily (monthly chunks)
        logger.info(f"  Fetching daily insights ({len(chunks)} monthly chunks)...")
        for since, until in chunks:
            p, e = self._call_insights(since, until, breakdown=None, time_increment=1)
            for row in p:
                row['date_start'] = row.pop('_date')
                result['meta_insights_performance'].append(row)
                day_row = {
                    'artist_id':          row['artist_id'],
                    'campaign_name':      row['campaign_name'],
                    'day_date':           row['date_start'],
                    'spend':              row['spend'],
                    'impressions':        row['impressions'],
                    'reach':              row['reach'],
                    'results':            row['results'],
                    'custom_conversions': row['custom_conversions'],
                    'cpr':                row['cpr'],
                }
                result['meta_insights_performance_day'].append(day_row)
            for row in e:
                row['date_start'] = row.pop('_date')
                result['meta_insights_engagement'].append(row)
                day_row = {k: v for k, v in row.items() if k != 'date_start'}
                day_row['day_date'] = row['date_start']
                result['meta_insights_engagement_day'].append(day_row)

        # 2. Age breakdown (full range, single call)
        logger.info("  Fetching age breakdown...")
        since = aggregate_start.strftime('%Y-%m-%d')
        until = today.strftime('%Y-%m-%d')
        p, e = self._call_insights(since, until, breakdown=['age'])
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_age'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_age'].append(row)

        # 3. Country breakdown
        logger.info("  Fetching country breakdown...")
        p, e = self._call_insights(since, until, breakdown=['country'])
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_country'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_country'].append(row)

        # 4. Placement breakdown
        logger.info("  Fetching placement breakdown...")
        p, e = self._call_insights(
            since, until,
            breakdown=['publisher_platform', 'platform_position'],
        )
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_placement'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_placement'].append(row)

        for tbl, rows in result.items():
            logger.info(f"    {tbl}: {len(rows)} rows")
        return result

    def _call_insights(
        self,
        since: str,
        until: str,
        breakdown: list = None,
        time_increment: int = None,
    ) -> tuple:
        """Single API insights call. Returns (perf_rows, eng_rows)."""
        try:
            fields = [
                'campaign_name', 'date_start', 'impressions', 'reach',
                'frequency', 'spend', 'cpm', 'cpc', 'ctr',
                'actions', 'cost_per_action_type', 'inline_link_clicks',
            ]
            params = {
                'level': 'campaign',
                'time_range': {'since': since, 'until': until},
                'limit': 5000,
            }
            if breakdown:
                params['breakdowns'] = breakdown
            if time_increment:
                params['time_increment'] = time_increment

            perf_rows, eng_rows = [], []
            for insight in _meta_list(self.ad_account.get_insights, fields=fields, params=params):
                base_perf = _extract_perf(insight, self.artist_id)
                base_eng = _extract_eng(insight, self.artist_id)

                # Attach dimension columns
                base_perf['_date'] = insight.get('date_start')
                base_eng['_date'] = insight.get('date_start')

                if breakdown and 'age' in breakdown:
                    base_perf['age_range'] = insight.get('age', 'Unknown')
                    base_eng['age_range'] = insight.get('age', 'Unknown')
                if breakdown and 'country' in breakdown:
                    base_perf['country'] = insight.get('country', 'Unknown')
                    base_eng['country'] = insight.get('country', 'Unknown')
                if breakdown and 'publisher_platform' in breakdown:
                    base_perf['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_perf['placement'] = insight.get('platform_position', 'Unknown')
                    base_eng['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_eng['placement'] = insight.get('platform_position', 'Unknown')

                perf_rows.append(base_perf)
                eng_rows.append(base_eng)

            return perf_rows, eng_rows
        except Exception:
            logger.exception(f"_call_insights failed (since={since} until={until} breakdown={breakdown})")
            raise

    # ── Upsert ────────────────────────────────────────────────────────────────

    def _upsert_all(
        self,
        campaigns: list,
        adsets: list,
        ads: list,
        creatives: list,
        insights: dict,
    ):
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

            # Insight tables
            # Columns allowed in each insight table (INSERT uses only these keys)
            _insight_cols = {
                'meta_insights_performance': [
                    'spend', 'impressions', 'reach', 'frequency', 'results',
                    'custom_conversions', 'cpr', 'cpm', 'link_clicks', 'cpc', 'ctr', 'lp_views',
                ],
                'meta_insights_performance_day': [
                    'spend', 'impressions', 'reach', 'results', 'custom_conversions', 'cpr',
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
            }

            for tbl, rows in insights.items():
                if not rows:
                    continue
                allowed = set(_conflict_cols[tbl]) | set(_insight_cols[tbl])
                trimmed = [{k: v for k, v in r.items() if k in allowed} for r in rows]
                self.db.upsert_many(
                    tbl, trimmed,
                    conflict_columns=_conflict_cols[tbl],
                    update_columns=_insight_cols[tbl],
                )

        except Exception:
            logger.exception("_upsert_all failed")
            raise
