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
from src.utils.safe_error import redact

from ._meta_config_fetch import _MetaConfigFetchMixin
from ._meta_constants import _CAMPAIGN_GRAIN_TABLES
from ._meta_insight_fetch import _MetaInsightFetchMixin
from ._meta_upsert import _MetaUpsertMixin

logger = logging.getLogger(__name__)

# Meta's own error fields, in the order an operator reads them. Never `str(exc)`:
# the SDK stringifies the PREPARED REQUEST, so its message carries the shared System
# User token. These four accessors return only what the API itself answered, and the
# request is not among them.
_META_ERROR_FIELDS = ("api_error_code", "api_error_subcode", "api_error_message")


def _account_failure_reason(exc: BaseException) -> str:
    """What to tell the operator about one failed ad account — the class AND the gesture.

    Measured 2026-09-03, on five consecutive nights of a real failure. `etl_run_log`
    and the nightly consolidated mail both said only
    `act_65390907 (FacebookRequestError)`. The reason was in the Airflow task log and
    nowhere else:

        (#200) Ad account owner has NOT grant ads_management or ads_read permission

    That sentence IS the gesture — the account owner shares the asset, nothing changes
    on our side. A class name alone sends the reader into the container to find it, so
    the alert named a symptom and withheld the action (ADR-011).

    Falls back to the class name for any exception that is not a Meta API error, which
    is what the previous code did for every one of them.
    """
    parts: list[str] | None = None
    if callable(getattr(exc, "api_error_code", None)):
        try:
            parts = [str(getattr(exc, f)()) for f in _META_ERROR_FIELDS]
        except Exception:  # noqa: BLE001 — a malformed SDK error must not mask the outage
            # Aucun `return` dans ce bloc, et ce n'est pas une préférence de style :
            # `audit_collectors_ast.py` refuse tout retour depuis un `except` d'un
            # module de `collectors/` (règle transverse #6). Le prédicat est plus
            # large que sa question — cette fonction ne collecte rien, elle met en
            # forme — mais un garde qu'on desserre pour se faire de la place ne garde
            # plus rien. La sentinelle coûte deux lignes ; l'exception coûterait la
            # classe entière.
            parts = None
    if parts is None:
        return type(exc).__name__
    code_s, subcode_s, message = parts
    if subcode_s not in ("", "None", "0"):
        code_s = f"{code_s}/{subcode_s}"
    # Redacted anyway: `api_error_message` is Meta's prose, but a message we have not
    # written is a message we do not get to assume is credential-free.
    return f"{type(exc).__name__} #{code_s}: {redact(message)}"[:300]


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
        # The account currently being collected. Read by `_prune_renamed_campaigns`
        # and stamped on every row (`_tag_account`); `None` only before `run()`.
        self._current_ad_account_id = None
        if ad_account is not None:
            # Injected SDK stub: the caller owns the account, so the multi-account
            # loop degenerates to that single one. Never rebuild it from creds —
            # that would reach for the real SDK in a test.
            self.ad_account = ad_account
            self._injected_ad_account = True
            self._current_ad_account_id = (self._creds.get('ad_account_ids') or
                                           [self._creds.get('ad_account_id')])[0]
        else:
            self._injected_ad_account = False
            self._init_api()
        self.db = db if db is not None else self._default_db()

    @staticmethod
    def _default_db():
        # The DSN is resolved in one place (R33). This used to default the host to
        # 'localhost', which is wrong inside Airflow — where this collector runs.
        from src.database.postgres_handler import PostgresHandler
        return PostgresHandler.from_env_or_config()

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
        # TENANT IDENTITY — no env fallback. META_AD_ACCOUNT_ID is the ADMIN's ad
        # account (docker-compose even hardcoded it as a default), so falling back
        # on it billed the admin's campaign data to this artist's artist_id.
        creds['account_id'] = (creds.get('account_id') or '').strip()
        missing = [k for k in ('access_token', 'app_id', 'app_secret', 'account_id')
                   if not creds.get(k)]
        if missing:
            raise ValueError(
                f"Meta credentials missing for artist_id={self.artist_id}: {missing}. "
                "Configure via Dashboard → Credentials → Meta."
            )
        # N comptes publicitaires (R53 / ADR-013). `ad_account_ids` est la liste
        # canonique ; `ad_account_id` reste le premier, pour tout ce qui lit un
        # scalaire. La normalisation `act_` vit dans `tenant_identity`, pas ici :
        # deux normalisations divergentes, c'est deux comptes différents pour la
        # même saisie, et un `ad_account_id` stampé qui ne correspond à aucun
        # discriminant de prune.
        from src.utils.tenant_identity import meta_ad_account_ids
        accounts = meta_ad_account_ids(creds)
        if not accounts:
            raise ValueError(
                f"Meta credentials missing for artist_id={self.artist_id}: "
                "['account_id']. Configure via Dashboard → Credentials → Meta."
            )
        creds['ad_account_ids'] = accounts
        creds['ad_account_id'] = accounts[0]
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
        self._ad_account_factory = AdAccount
        self._select_account(self._creds['ad_account_id'])
        logger.info(
            f"Meta API initialised — artist_id={self.artist_id} "
            f"accounts={self._creds.get('ad_account_ids', [])}"
        )

    def _select_account(self, ad_account_id: str) -> None:
        """Point the SDK — and the account stamp — at one ad account.

        The two move together on purpose. `self.ad_account` decides what the API
        RETURNS and `_current_ad_account_id` decides what the rows are WRITTEN and
        PRUNED under; setting one without the other writes account A's data under
        account B's discriminant, which the prune then deletes on the next pass.
        """
        self._current_ad_account_id = ad_account_id
        if not self._injected_ad_account:
            self.ad_account = self._ad_account_factory(ad_account_id)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, full_history: bool = False, insights_only: bool = False,
            fetch_creatives: bool = True) -> int:
        """Collect EVERY ad account this tenant declared. Returns total insight rows.

        One artist, N ad accounts (R53 / ADR-013) — the agency case. Each account is
        a full pass of `_run_one_account`, under its own `ad_account_id` stamp.

        **Une panne sur un compte ne fait pas perdre les autres.** Trois comptes dont
        un a perdu son partage d'asset : lever au premier échec ferait qu'aucun des
        deux comptes sains ne collecterait jamais, et le partage manquant est
        justement la panne la plus fréquente sur Meta. Les comptes sont donc tous
        parcourus, puis l'exception est levée à la fin avec la liste — la tâche
        Airflow reste ROUGE (règle transverse #6 : un collecteur lève), et les
        données déjà écrites le restent, la persistance étant faite par tronçon.
        """
        accounts = list(self._creds.get('ad_account_ids') or [])
        if not accounts:
            # `_load_credentials` refuse déjà de rendre une liste vide ; ce chemin
            # n'est atteignable que par des creds injectés en test.
            accounts = [self._current_ad_account_id]
        total = 0
        failures: list[tuple] = []
        for index, account in enumerate(accounts, start=1):
            self._select_account(account)
            logger.info(
                f"Meta collect — artist_id={self.artist_id} account {index}/"
                f"{len(accounts)} ({account})"
            )
            try:
                total += self._run_one_account(
                    full_history=full_history, insights_only=insights_only,
                    fetch_creatives=fetch_creatives,
                )
            except Exception as exc:
                # Jamais `str(exc)` dans le journal : le message d'une erreur réseau
                # de la SDK Meta embarque l'URL préparée, donc le token partagé.
                logger.exception(f"Meta collect FAILED on account {account}")
                failures.append((account, _account_failure_reason(exc)))
        if failures:
            detail = ", ".join(f"{a} ({e})" for a, e in failures)
            raise RuntimeError(
                f"Meta collect: {len(failures)}/{len(accounts)} ad account(s) failed "
                f"for artist_id={self.artist_id} — {detail}. "
                f"{total} insight rows were still written by the accounts that worked."
            )
        return total

    def _run_one_account(self, full_history: bool = False, insights_only: bool = False,
                         fetch_creatives: bool = True) -> int:
        """Full collection pipeline for the CURRENTLY selected ad account.

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
                # Scopé au compte courant : sans ça, la passe du compte B
                # recalculerait ses dates de départ sur les campagnes de A, et le
                # prune de B verrait la liste de A comme « campagnes disparues ».
                "SELECT campaign_id, campaign_name, start_time, objective FROM meta_campaigns "
                "WHERE artist_id = %s AND ad_account_id IS NOT DISTINCT FROM %s",
                (self.artist_id, self._current_ad_account_id),
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
            f"Meta API collect done — artist_id={self.artist_id} "
            f"account={self._current_ad_account_id}: "
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
