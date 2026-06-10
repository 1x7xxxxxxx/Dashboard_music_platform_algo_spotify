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

Decomposed (move-only, zero behaviour change): pure helpers live in _meta_retry /
_meta_parsers, shared constants in _meta_constants, and the fetch/upsert methods are
split across _MetaConfigFetchMixin / _MetaInsightFetchMixin / _MetaUpsertMixin. The
helper symbols are re-exported below so consumers (debug_dag, tests) keep importing
them from this module.
"""
import logging
import os

from src.utils.meta_config import META_API_VERSION

from ._meta_config_fetch import _MetaConfigFetchMixin
from ._meta_constants import _CAMPAIGN_GRAIN_TABLES
from ._meta_insight_fetch import _MetaInsightFetchMixin
from ._meta_upsert import _MetaUpsertMixin

logger = logging.getLogger(__name__)


class MetaAdsApiCollector(_MetaConfigFetchMixin, _MetaInsightFetchMixin, _MetaUpsertMixin):
    """Full Meta Ads API collector. No CSV dependency."""

    def __init__(self, artist_id: int, *, db=None, ad_account=None, creds=None):
        """Production path: loads creds, inits the Meta SDK, connects Postgres.

        Test seam (keyword-only, defaults preserve prod behaviour): inject a fake
        `db`, `ad_account` (stub Meta SDK) and/or `creds` to exercise the pipeline
        without real Meta tokens or a live DB. See tests/fakes/meta_sdk.py.
        """
        if not artist_id or artist_id < 1:
            raise ValueError(f"MetaAdsApiCollector: invalid artist_id={artist_id!r}")
        self.artist_id = artist_id
        self._creds = creds if creds is not None else self._load_credentials()
        if ad_account is not None:
            self.ad_account = ad_account
        else:
            self._init_api()
        self.db = db if db is not None else self._default_db()

    @staticmethod
    def _default_db():
        from src.database.postgres_handler import PostgresHandler
        return PostgresHandler(
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
        # Shared System User app falls back to env, so an artist only needs to
        # provide their own account_id. Per-artist stored values always win
        # (additive — existing tenants are unchanged).
        creds['access_token'] = creds.get('access_token') or os.getenv('META_ACCESS_TOKEN')
        creds['app_id'] = creds.get('app_id') or os.getenv('META_APP_ID')
        creds['app_secret'] = creds.get('app_secret') or os.getenv('META_APP_SECRET')
        creds['account_id'] = creds.get('account_id') or os.getenv('META_AD_ACCOUNT_ID')
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

            # Persist config tables up front, before the long insight fetch: a throttle
            # mid-insights then can't discard the campaign/adset/ad/creative work.
            self._upsert_config(campaigns, adsets, ads, creatives)
            # Drop rows orphaned by a campaign rename (campaign-grain tables key by name).
            self._prune_renamed_campaigns(campaigns)

        # adsets/ads (or DB fallback in insights_only) resolve each insight's optimization
        # goal → its native "result" action. See _build_goal_maps / _results_for_goal.
        # persist_cb upserts each chunk/breakdown as it is fetched, so a late throttle
        # keeps all earlier insights (no more all-or-nothing run).
        insights = self._fetch_all_insights(
            campaigns, adsets=adsets, ads=ads, full_history=full_history,
            persist_cb=self._persist_insights,
        )

        total_insight_rows = sum(len(v) for v in insights.values())
        logger.info(
            f"Meta API collect done — artist_id={self.artist_id}: "
            f"{len(campaigns)} campaigns, {len(adsets)} adsets, {len(ads)} ads, "
            f"{len(creatives)} creatives, {total_insight_rows} insight rows across "
            f"{len(insights)} tables"
        )
        return total_insight_rows


# ── Re-exports for backward compatibility ─────────────────────────────────────
# Consumers (airflow/debug_dag/debug_meta_ads_api.py, tests) import these symbols
# from this module; keep them importable here after the move to leaf helper modules.
from ._meta_parsers import (  # noqa: E402
    _extract_eng,
    _extract_perf,
    _is_conversion_goal,
    _results_for_goal,
)
from ._meta_retry import _meta_list, _meta_retry  # noqa: E402

__all__ = [
    'MetaAdsApiCollector',
    '_CAMPAIGN_GRAIN_TABLES',
    '_extract_eng',
    '_extract_perf',
    '_is_conversion_goal',
    '_meta_list',
    '_meta_retry',
    '_results_for_goal',
]
