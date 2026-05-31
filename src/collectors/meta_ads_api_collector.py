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
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date, timezone
from dateutil.relativedelta import relativedelta
from src.utils.meta_config import META_API_VERSION

logger = logging.getLogger(__name__)

# Meta throttling error codes (all transient, safe to retry with backoff):
#   17    — user-level rate limit
#   4     — app-level request limit ("Application request limit reached")
#   80004 — ads-management business-use-case throttle ("too many calls to this ad-account")
#   32    — page-level rate limit
# A backfill that includes archived ads multiplies call volume, so the run must
# back off on ALL of these — handling only code 17 made the placement-insights call
# hard-fail on code 4.
_META_THROTTLE_CODES = frozenset({4, 17, 32, 80004})
_META_RATE_LIMIT_WAIT = 60  # base seconds; multiplied per attempt (exponential)

# Meta retains insights for 37 months; a time_range start beyond that returns API
# error #3018. We clamp the backfill floor to 36 months — one month inside the hard
# limit so a request never trips on time-of-day/timezone boundary rounding. Archived
# campaigns (now in scope via the broadened status filters) can carry very old or
# even epoch start_time values, which would otherwise push the backfill to 1970.
_META_INSIGHTS_RETENTION_MONTHS = 36

# effective_status allowlists per object level. A PAUSED *campaign* propagates
# CAMPAIGN_PAUSED to its ad sets and CAMPAIGN_PAUSED/ADSET_PAUSED to its ads — those
# values are NOT 'PAUSED', so a ['ACTIVE','PAUSED'] filter silently excludes every
# ad of a paused/archived campaign. The ad would then be absent from meta_ads, and
# its ad-level insights (which the API *does* return) get dropped by the ad_id FK
# guard in _fetch_ad_insights → campaign-level spend present, per-creative detail
# missing. Include the paused/archived states so historical ads are refreshed.
_CAMPAIGN_STATUSES = ['ACTIVE', 'PAUSED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES']
_ADSET_STATUSES = ['ACTIVE', 'PAUSED', 'CAMPAIGN_PAUSED', 'ARCHIVED',
                   'IN_PROCESS', 'WITH_ISSUES']
_AD_STATUSES = ['ACTIVE', 'PAUSED', 'CAMPAIGN_PAUSED', 'ADSET_PAUSED', 'ARCHIVED',
                'IN_PROCESS', 'WITH_ISSUES']


def _meta_retry(callable_fn, *args, max_retries: int = 4, **kwargs):
    """Call a facebook_business SDK method, retrying any throttle code with exponential backoff.

    Works for both list edges (get_insights, get_ads…) and single-object reads
    (AdCreative.api_get). Returns the callable's raw result.
    """
    from facebook_business.exceptions import FacebookRequestError
    for attempt in range(1, max_retries + 1):
        try:
            return callable_fn(*args, **kwargs)
        except FacebookRequestError as exc:
            if exc.api_error_code() in _META_THROTTLE_CODES and attempt < max_retries:
                wait = _META_RATE_LIMIT_WAIT * (2 ** (attempt - 1))  # 60s, 120s, 240s
                logger.warning(
                    f"Meta throttle (code {exc.api_error_code()}) — attempt "
                    f"{attempt}/{max_retries}. Waiting {wait}s before retry..."
                )
                time.sleep(wait)
            else:
                raise


def _meta_list(callable_fn, *args, **kwargs) -> list:
    """Throttle-aware list call — materialises the cursor INSIDE the retry loop.

    The SDK raises during cursor iteration (load_next_page), so list() must run
    within _meta_retry or a paging throttle would escape un-retried.
    """
    return _meta_retry(lambda: list(callable_fn(*args, **kwargs)))

# "Results" = Meta's native result, which keys off the AD SET's optimization_goal
# (mirrors the "Results" column in Ads Manager — Meta counts the optimization event).
# Each goal maps to the action_type that counts as its result. The special sentinel
# 'offsite_conversion' is a PREFIX match: it sums every action_type starting with
# 'offsite_conversion.' (custom + pixel + id-suffixed variants like
# 'offsite_conversion.custom.1234567890'), because Meta appends the conversion id to
# the action_type — an exact match on 'offsite_conversion.custom' silently returns 0.
# None means the goal has no action-based result (reach/impressions/awareness).
_OFFSITE_PREFIX = 'offsite_conversion'

_GOAL_RESULT_ACTION = {
    'OFFSITE_CONVERSIONS':  _OFFSITE_PREFIX,
    'ONSITE_CONVERSIONS':   'onsite_conversion',
    'LEAD_GENERATION':      _OFFSITE_PREFIX,
    'QUALITY_LEAD':         _OFFSITE_PREFIX,
    'LINK_CLICKS':          'link_click',
    'LANDING_PAGE_VIEWS':   'landing_page_view',
    'POST_ENGAGEMENT':      'post_engagement',
    'PAGE_LIKES':           'like',
    'THRUPLAY':             'video_view',
    'VIDEO_VIEWS':          'video_view',
    'REACH':                None,
    'IMPRESSIONS':          None,
    'AD_RECALL_LIFT':       None,
}

# Goals whose result is a (paid) conversion → CPR ("cost per result") is meaningful.
# For engagement/traffic/reach goals CPR is suppressed (would imply a conversion).
_CONVERSION_GOALS = frozenset([
    'OFFSITE_CONVERSIONS', 'ONSITE_CONVERSIONS', 'LEAD_GENERATION', 'QUALITY_LEAD',
])


def _results_for_goal(actions: dict, goal: str) -> int:
    """Sum the action(s) that count as the campaign's result for a given optimization goal.

    Falls back to offsite-conversion prefix sum for unknown goals (best effort, never
    silently 0 for a goal we simply haven't mapped). Returns 0 for reach/impression goals.
    """
    g = (goal or '').upper()
    if g in _GOAL_RESULT_ACTION:
        match = _GOAL_RESULT_ACTION[g]
        if match is None:
            return 0
    else:
        match = _OFFSITE_PREFIX  # unknown goal → assume conversion intent
    if match in (_OFFSITE_PREFIX, 'onsite_conversion'):
        return sum(v for k, v in actions.items() if k.startswith(match))
    return actions.get(match, 0)


def _is_conversion_goal(goal: str) -> bool:
    """True if the goal's result is a (paid) conversion → CPR is meaningful.

    Unknown goals are treated as conversion intent, mirroring _results_for_goal's fallback.
    """
    g = (goal or '').upper()
    if g in _GOAL_RESULT_ACTION:
        return _GOAL_RESULT_ACTION[g] in (_OFFSITE_PREFIX, 'onsite_conversion')
    return True


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

def _extract_perf(insight, artist_id: int, goal: str = None) -> dict:
    spend = float(insight.get('spend') or 0)
    impressions = int(insight.get('impressions') or 0)
    reach = int(insight.get('reach') or 0)
    frequency = float(insight.get('frequency') or 0)
    link_clicks = int(insight.get('inline_link_clicks') or 0)
    cpm_raw = float(insight.get('cpm') or 0)
    ctr = float(insight.get('ctr') or 0)

    # Aggregate every action type once (action_type → summed value).
    actions = {}
    for action in (insight.get('actions') or []):
        atype = action['action_type']
        actions[atype] = actions.get(atype, 0) + int(float(action['value']))

    # custom_conversions = Spotify button clicks via Hypeddit CAPI. Prefix match catches
    # the id-suffixed action_type ('offsite_conversion.custom.<id>') Meta actually returns.
    custom_conversions = sum(
        v for k, v in actions.items() if k.startswith('offsite_conversion.custom')
    )
    lp_views = actions.get('landing_page_view', 0)

    # results = Meta's native result for this ad set's optimization goal.
    results = _results_for_goal(actions, goal)

    # CPR ("cost per result") is only meaningful for conversion goals — suppressed
    # otherwise so an engagement/traffic cost-per-action is not mistaken for a conversion CPR.
    cpr = round(spend / results, 4) if (_is_conversion_goal(goal) and results > 0) else None

    return {
        'artist_id':          artist_id,
        'campaign_name':      insight.get('campaign_name', ''),
        'spend':              spend,
        'impressions':        impressions,
        'reach':              reach,
        'frequency':          frequency,
        'results':            results,
        'custom_conversions': custom_conversions,
        'cpr':                cpr,
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
            api_version=META_API_VERSION,
        )
        self.ad_account = AdAccount(self._creds['ad_account_id'])
        logger.info(
            f"Meta API initialised — artist_id={self.artist_id} "
            f"account={self._creds['ad_account_id']}"
        )

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, full_history: bool = False, insights_only: bool = False,
            fetch_creatives: bool = True) -> int:
        """Full collection pipeline. Returns total insight rows inserted.

        full_history=False  : smart incremental — starts from MAX(day_date)-3d in DB,
                              falls back to earliest campaign start on first run.
        full_history=True   : force backfill from earliest campaign start_time to today.
        insights_only=True  : skip campaigns/adsets/ads/creatives fetch (already in DB);
                              only run the 4 insight API calls. Reduces API call count by ~75%.
                              Requires at least one prior full run to have populated config tables.
        fetch_creatives=False: skip the per-creative content fetch (title/body/CTA). That
                              loop is one API call PER creative — the dominant rate-limit
                              driver on a full_history backfill — and the Créatives view
                              does not display those columns. Skip it to stay under the
                              account throttle when backfilling many archived ads.
        """
        if insights_only:
            # Load campaign list from DB (needed for full_history start-date calculation)
            campaigns_db = self.db.fetch_query(
                "SELECT campaign_id, campaign_name, start_time, objective FROM meta_campaigns "
                "WHERE artist_id = %s",
                (self.artist_id,),
            )
            campaigns = [
                {'campaign_id': r[0], 'campaign_name': r[1],
                 'start_time': str(r[2]) if r[2] else None, 'objective': r[3]}
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

            creatives = self._fetch_creatives(ads) if fetch_creatives else []
            if not fetch_creatives:
                logger.info("  creative content fetch skipped (fetch_creatives=False)")

        # adsets/ads (or DB fallback in insights_only) resolve each insight's optimization
        # goal → its native "result" action. See _build_goal_maps / _results_for_goal.
        insights = self._fetch_all_insights(
            campaigns, adsets=adsets, ads=ads, full_history=full_history,
        )

        self._upsert_all(campaigns, adsets, ads, creatives, insights)

        total_insight_rows = sum(len(v) for v in insights.values())
        logger.info(
            f"Meta API collect done — artist_id={self.artist_id}: "
            f"{len(campaigns)} campaigns, {len(adsets)} adsets, {len(ads)} ads, "
            f"{len(creatives)} creatives, {total_insight_rows} insight rows across "
            f"{len(insights)} tables"
        )
        return total_insight_rows

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

    # ── Fetch: insights (all 10 tables) ──────────────────────────────────────

    def _fetch_all_insights(self, campaigns: list, adsets: list = None,
                            ads: list = None, full_history: bool = False) -> dict:
        """Return {table_name: [rows]} for all 11 insight tables.

        Per time chunk: campaign daily/global + ad-level (meta_insights). Plus 3 aggregate
        breakdown calls (age/country/placement). The result action for each row is resolved
        from the ad set optimization goal (campaign-dominant goal for campaign-level rows,
        exact per-ad goal for ad-level rows).
        """
        today = date.today()

        # Resolve optimization goals: dominant per campaign, exact per ad/adset.
        goal_by_campaign, goal_by_ad, goal_by_adset = self._build_goal_maps(
            campaigns, adsets or [], ads or [],
        )

        def _earliest_campaign_start() -> date:
            """Return the earliest campaign start_time, fallback to 1 year ago."""
            starts = []
            for c in campaigns:
                s = c.get('start_time')
                if s:
                    try:
                        starts.append(datetime.fromisoformat(s[:10]).date())
                    except Exception:
                        pass
            return min(starts) if starts else today - timedelta(days=365)

        if full_history:
            history_start = _earliest_campaign_start()
        else:
            # Smart incremental: start from last known data point (minus 3-day overlap
            # to catch late-arriving Meta data), falling back to full history on first run.
            row = self.db.fetch_query(
                "SELECT MAX(day_date) FROM meta_insights_performance_day WHERE artist_id = %s",
                (self.artist_id,),
            )
            last_day = row[0][0] if row and row[0][0] else None
            if last_day is not None:
                history_start = last_day - timedelta(days=3)
            else:
                # No data yet — backfill from first campaign
                history_start = _earliest_campaign_start()
                logger.info(
                    f"No existing insight data for artist_id={self.artist_id} — "
                    f"backfilling from {history_start}"
                )

        # Clamp to Meta's insights retention window (API error #3018 otherwise).
        retention_floor = today - relativedelta(months=_META_INSIGHTS_RETENTION_MONTHS)
        if history_start < retention_floor:
            logger.info(
                f"Clamping backfill start {history_start} → {retention_floor} "
                f"(Meta {_META_INSIGHTS_RETENTION_MONTHS}-month insights retention)"
            )
            history_start = retention_floor

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
            'meta_insights':                       [],  # ad-level (Créatives view)
            # Ad/adset-level breakdowns (multi-grain Breakdowns view) — perf + engagement.
            'meta_insights_performance_ad_country':      [],
            'meta_insights_engagement_ad_country':       [],
            'meta_insights_performance_ad_placement':    [],
            'meta_insights_engagement_ad_placement':     [],
            'meta_insights_performance_ad_age':          [],
            'meta_insights_engagement_ad_age':           [],
            'meta_insights_performance_adset_country':   [],
            'meta_insights_engagement_adset_country':    [],
            'meta_insights_performance_adset_placement': [],
            'meta_insights_engagement_adset_placement':  [],
            'meta_insights_performance_adset_age':       [],
            'meta_insights_engagement_adset_age':        [],
        }

        # 1. Global / daily (monthly chunks) + ad-level
        logger.info(f"  Fetching daily insights ({len(chunks)} monthly chunks)...")
        for since, until in chunks:
            result['meta_insights'].extend(
                self._fetch_ad_insights(since, until, goal_by_ad)
            )
            p, e = self._call_insights(since, until, breakdown=None, time_increment=1,
                                       goal_by_campaign=goal_by_campaign)
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
                    'collected_at':       datetime.now(timezone.utc),
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
        p, e = self._call_insights(since, until, breakdown=['age'],
                                   goal_by_campaign=goal_by_campaign)
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_age'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_age'].append(row)

        # 3. Country breakdown
        logger.info("  Fetching country breakdown...")
        p, e = self._call_insights(since, until, breakdown=['country'],
                                   goal_by_campaign=goal_by_campaign)
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
            goal_by_campaign=goal_by_campaign,
        )
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_placement'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_placement'].append(row)

        # 5. Ad-level & adset-level breakdowns (full range, one call per dim×level —
        #    each call yields BOTH perf and engagement rows). Powers the Breakdowns view.
        _bd_levels = (('ad', 'ad_id', goal_by_ad), ('adset', 'adset_id', goal_by_adset))
        _bd_dims = (
            (['country'], 'country'),
            (['publisher_platform', 'platform_position'], 'placement'),
            (['age'], 'age'),
        )
        for level, id_field, goal_map in _bd_levels:
            for breakdown, suffix in _bd_dims:
                logger.info(f"  Fetching {level} {suffix} breakdown...")
                p, e = self._fetch_breakdown(since, until, level, id_field, breakdown, goal_map)
                result[f'meta_insights_performance_{level}_{suffix}'] = p
                result[f'meta_insights_engagement_{level}_{suffix}'] = e

        for tbl, rows in result.items():
            logger.info(f"    {tbl}: {len(rows)} rows")
        return result

    def _call_insights(
        self,
        since: str,
        until: str,
        breakdown: list = None,
        time_increment: int = None,
        goal_by_campaign: dict = None,
    ) -> tuple:
        """Single campaign-level API insights call. Returns (perf_rows, eng_rows)."""
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
                goal = (goal_by_campaign or {}).get(insight.get('campaign_name'))
                base_perf = _extract_perf(insight, self.artist_id, goal)
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

    def _fetch_breakdown(self, since: str, until: str, level: str, id_field: str,
                         breakdown: list, goal_by_entity: dict) -> tuple:
        """Ad-level OR adset-level breakdown (country/placement/age). Returns (perf, eng).

        Single full-range aggregate call (like the campaign breakdowns). Keyed by
        ad_id/adset_id; only entities already in meta_ads/meta_adsets (present in
        goal_by_entity) are kept, to honour the FK. Results/CPR use the entity's exact
        optimization goal. The junk `campaign_name` from _extract_* is trimmed at upsert.
        """
        try:
            fields = [
                id_field, 'date_start', 'impressions', 'reach', 'spend', 'frequency',
                'cpm', 'cpc', 'ctr', 'actions', 'cost_per_action_type', 'inline_link_clicks',
            ]
            params = {
                'level': level,
                'time_range': {'since': since, 'until': until},
                'breakdowns': breakdown,
                'limit': 5000,
            }
            perf_rows, eng_rows = [], []
            for insight in _meta_list(self.ad_account.get_insights, fields=fields, params=params):
                eid = insight.get(id_field)
                if not eid or eid not in goal_by_entity:
                    continue  # unknown entity → would violate the ad_id/adset_id FK
                goal = goal_by_entity.get(eid)
                base_perf = _extract_perf(insight, self.artist_id, goal)
                base_eng = _extract_eng(insight, self.artist_id)
                base_perf[id_field] = eid
                base_eng[id_field] = eid

                if 'age' in breakdown:
                    base_perf['age_range'] = insight.get('age', 'Unknown')
                    base_eng['age_range'] = insight.get('age', 'Unknown')
                if 'country' in breakdown:
                    base_perf['country'] = insight.get('country', 'Unknown')
                    base_eng['country'] = insight.get('country', 'Unknown')
                if 'publisher_platform' in breakdown:
                    base_perf['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_perf['placement'] = insight.get('platform_position', 'Unknown')
                    base_eng['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_eng['placement'] = insight.get('platform_position', 'Unknown')

                perf_rows.append(base_perf)
                eng_rows.append(base_eng)
            return perf_rows, eng_rows
        except Exception:
            logger.exception(
                f"_fetch_breakdown failed (level={level} breakdown={breakdown} "
                f"since={since} until={until})"
            )
            raise

    # ── Goal resolution + ad-level insights ────────────────────────────────────

    def _build_goal_maps(self, campaigns: list, adsets: list, ads: list) -> tuple:
        """Return (goal_by_campaign, goal_by_ad, goal_by_adset).

        goal_by_campaign uses the DOMINANT optimization_goal among a campaign's ad sets
        (campaign-level insights cannot be split per ad set). goal_by_ad and goal_by_adset
        are exact. Falls back to the DB when adsets/ads are not provided (insights_only).
        """
        if not adsets:
            rows = self.db.fetch_query(
                "SELECT adset_id, campaign_id, optimization_goal "
                "FROM meta_adsets WHERE artist_id = %s",
                (self.artist_id,),
            )
            adsets = [{'adset_id': r[0], 'campaign_id': r[1], 'optimization_goal': r[2]}
                      for r in (rows or [])]
        if not ads:
            rows = self.db.fetch_query(
                "SELECT ad_id, adset_id FROM meta_ads WHERE artist_id = %s",
                (self.artist_id,),
            )
            ads = [{'ad_id': r[0], 'adset_id': r[1]} for r in (rows or [])]

        cid_to_name = {c['campaign_id']: c['campaign_name'] for c in campaigns}
        goal_by_adset = {a['adset_id']: a.get('optimization_goal') for a in adsets}

        counter = defaultdict(Counter)
        for a in adsets:
            goal = a.get('optimization_goal')
            cname = cid_to_name.get(a.get('campaign_id'))
            if goal and cname:
                counter[cname][goal] += 1
        goal_by_campaign = {cn: c.most_common(1)[0][0] for cn, c in counter.items()}

        goal_by_ad = {ad['ad_id']: goal_by_adset.get(ad['adset_id']) for ad in ads}
        return goal_by_campaign, goal_by_ad, goal_by_adset

    def _fetch_ad_insights(self, since: str, until: str, goal_by_ad: dict) -> list:
        """Ad-level daily insights → rows for meta_insights (powers the Créatives view).

        `conversions` = the ad set goal's native result (via _results_for_goal); only ads
        already known in meta_ads (present in goal_by_ad) are kept, to honour the ad_id FK.
        """
        try:
            fields = [
                'ad_id', 'date_start', 'impressions', 'clicks', 'spend', 'reach',
                'frequency', 'cpc', 'cpm', 'ctr', 'actions',
            ]
            params = {
                'level': 'ad',
                'time_range': {'since': since, 'until': until},
                'time_increment': 1,
                'limit': 5000,
            }
            rows = []
            for insight in _meta_list(self.ad_account.get_insights, fields=fields, params=params):
                ad_id = insight.get('ad_id')
                if not ad_id or ad_id not in goal_by_ad:
                    continue  # unknown ad → would violate meta_insights.ad_id FK
                actions = {}
                for action in (insight.get('actions') or []):
                    atype = action['action_type']
                    actions[atype] = actions.get(atype, 0) + int(float(action['value']))

                goal = goal_by_ad.get(ad_id)
                conversions = _results_for_goal(actions, goal)
                spend = float(insight.get('spend') or 0)
                is_conversion = _is_conversion_goal(goal)
                rows.append({
                    'artist_id':           self.artist_id,
                    'ad_id':               ad_id,
                    'date':                insight.get('date_start'),
                    'impressions':         int(insight.get('impressions') or 0),
                    'clicks':              int(insight.get('clicks') or 0),
                    'spend':               spend,
                    'reach':               int(insight.get('reach') or 0),
                    'frequency':           float(insight.get('frequency') or 0),
                    'cpc':                 float(insight.get('cpc') or 0),
                    'cpm':                 float(insight.get('cpm') or 0),
                    'ctr':                 float(insight.get('ctr') or 0),
                    'conversions':         conversions,
                    'cost_per_conversion': (round(spend / conversions, 4)
                                            if (is_conversion and conversions > 0) else 0),
                })
            return rows
        except Exception:
            logger.exception(f"_fetch_ad_insights failed (since={since} until={until})")
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
