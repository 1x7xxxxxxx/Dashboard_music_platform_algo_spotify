from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

sys.path.insert(0, '/opt/airflow')

# Redact credentials out of any exception this module logs: an HTTP
# exception message embeds the prepared URL, and several upstream APIs take
# their credential as a QUERY PARAMETER. stdlib-only, safe at DAG parse time.
from src.utils.safe_error import safe_error

import logging
logger = logging.getLogger(__name__)


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {safe_error(e)}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}

def precheck_instagram_credentials(**context):
    """Informational pre-check — never fails the fleet.

    Central-app model: the Instagram access token is admin-owned (META_ACCESS_TOKEN env,
    shared System User app). An artist connects Instagram by supplying their ig_user_id
    (Instagram Business Account). Artists without an ig_user_id simply haven't connected
    Instagram → skip them, never block the other tenants. The fail-if-all-failed decision
    lives in the collector (per-artist isolation).
    """
    import os
    from src.utils.credential_loader import get_active_artists, load_platform_credentials

    artists = get_active_artists()
    if not artists:
        logger.info("No active artists — skipping credential pre-check.")
        return

    if not os.getenv('META_ACCESS_TOKEN'):
        logger.warning("Shared Meta/Instagram token (META_ACCESS_TOKEN) not configured "
                       "— admin action required.")

    connected = [name for aid, name in artists
                 if load_platform_credentials(aid, 'meta').get('ig_user_id')]
    logger.info(f"✅ Instagram: {len(connected)}/{len(artists)} artist(s) connected "
                "(have an ig_user_id).")


def run_insta_collector(**context):
    import os
    import logging
    from src.collectors.instagram_api_collector import InstagramCollector
    from src.utils.credential_loader import load_platform_credentials, get_active_artists

    logger = logging.getLogger(__name__)

    conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
    artist_id_conf = conf.get('artist_id')

    artists = get_active_artists(include_artist_id=artist_id_conf)
    if not artists:
        if os.getenv('LEGACY_SINGLE_TENANT') == '1':
            logger.info("No active artist — LEGACY_SINGLE_TENANT=1, using env identity as tenant 1")
            artists = [(1, 'default')]
        else:
            logger.info("No active artist in DB — nothing to collect.")
            return

    from src.utils.dag_run_logger import (
        record_tenant_failure, record_tenant_skip, record_tenant_success,
    )
    run_id = context.get('run_id', '') if context else ''

    configured = 0
    succeeded = 0
    per_artist_errors = []  # multi-tenant isolation — one bad tenant must not abort the fleet

    for artist_id, artist_name in artists:
        creds = load_platform_credentials(artist_id, 'meta')
        ig_user_id = creds.get('ig_user_id')
        token = creds.get('access_token') or os.getenv('META_ACCESS_TOKEN')

        # Every branch below leaves a row in etl_run_log — see dag_run_logger.
        if not ig_user_id:
            logger.info(f"  {artist_name} (id={artist_id}) sans ig_user_id — skip")
            record_tenant_skip('instagram_daily', artist_id, 'instagram',
                               'no Instagram Business Account ID declared', run_id)
            continue
        if not token:
            logger.warning(f"  {artist_name} (id={artist_id}) — token Meta partagé absent "
                           "(META_ACCESS_TOKEN) — contacter admin ; skip")
            per_artist_errors.append((artist_id, artist_name, "shared token missing (admin)"))
            record_tenant_skip('instagram_daily', artist_id, 'instagram',
                               'shared Meta token missing (admin action)', run_id)
            continue

        # Passed as arguments, not through os.environ: the conditional writes below
        # used to leak artist A's app credentials to artist B (only set when the
        # current artist had one), and left them in the worker process afterwards.

        configured += 1
        logger.info(f"Instagram collect — artist_id={artist_id} ({artist_name})")
        try:
            rows = InstagramCollector(
                artist_id=artist_id,
                access_token=token,
                ig_user_id=ig_user_id,
                app_id=creds.get('app_id'),
                app_secret=creds.get('app_secret'),
            ).run() or 0
            record_tenant_success('instagram_daily', artist_id, 'instagram', rows, run_id)
            succeeded += 1
            logger.info(f"  Collect done for {artist_name}")
        except Exception as e:
            # Per-artist isolation: the collector still raises (rule #6); the loop
            # absorbs it per-tenant so a single failure can't blank the others.
            logger.error(f"  Error for {artist_name}: {safe_error(e)}")
            per_artist_errors.append((artist_id, artist_name, safe_error(e)[:200]))
            record_tenant_failure('instagram_daily', artist_id, 'instagram', e, run_id)
            continue

    if per_artist_errors:
        summary = '; '.join(f'{aid}/{name}: {err}' for aid, name, err in per_artist_errors)
        logger.warning(f"Instagram: {len(per_artist_errors)} artist(s) failed (isolated): {summary}")

    # Fail only if EVERY connected artist failed (admin-level signal), never on one tenant.
    if configured > 0 and succeeded == 0:
        raise ValueError(
            "Instagram collection failed for every connected artist: "
            + '; '.join(f'{aid}/{name}: {err}' for aid, name, err in per_artist_errors)
        )

with DAG(
    'instagram_daily',
    default_args=default_args,
    description='Collecte journalière Instagram',
    schedule='0 10 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,  # concurrent runs hammer the same Meta/IG Graph API → throttle
    tags=['social', 'instagram']
) as dag:

    precheck_task = PythonOperator(
        task_id='precheck_credentials',
        python_callable=precheck_instagram_credentials,
    )

    collect_task = PythonOperator(
        task_id='collect_instagram_stats',
        python_callable=run_insta_collector,
    )

    precheck_task >> collect_task
