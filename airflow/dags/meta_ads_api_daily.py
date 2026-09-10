"""DAG: meta_ads_api_daily — daily pull from Meta Marketing API.

Brick 23: replaces manual CSV upload as primary data source for Meta Ads.
Schedule: 05:00 UTC daily.
Skips artists with no Meta credentials (WARNING log, no failure).
Raises if the collector fails for an artist that has credentials.
"""
import sys
import os
import logging

sys.path.insert(0, '/opt/airflow')

# Redact credentials out of any exception this module logs: an HTTP
# exception message embeds the prepared URL, and several upstream APIs take
# their credential as a QUERY PARAMETER. stdlib-only, safe at DAG parse time.
from src.utils.safe_error import safe_error
from src.utils.dag_timeouts import dagrun_timeout_for

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

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


def run_meta_api_collector(**context):
    from src.collectors.meta_ads_api_collector import MetaAdsApiCollector
    from src.utils.credential_loader import get_active_artists, load_platform_credentials

    conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
    artist_id_conf = conf.get('artist_id')
    artists = get_active_artists(include_artist_id=artist_id_conf)

    if not artists:
        logger.info("No active artists — skipping.")
        return

    configured = 0
    succeeded = 0
    errors = []
    # UN COMPTE PUBLICITAIRE N'EST COLLECTÉ QU'UNE FOIS PAR NUIT.
    #
    # Le bac à sable déclare le compte du profil principal — c'est sa raison d'être, il
    # est exempté du garde d'unicité d'identité. La collecte le reprenait donc à
    # l'identique, et Meta la limitait : mesuré sur le run du 09-09, **535 s pour le
    # second locataire dont 424 s de sommeil imposé**, contre 96 s pour le premier, sur
    # le MÊME compte. Meta pesait 528 s des 651 s d'ETL nocturne — 81 %.
    #
    # On saute donc la reprise, et on le DIT. Conséquence assumée : les lignes déjà
    # écrites sous le second locataire ne sont plus rafraîchies. C'est acceptable pour
    # un locataire d'essai, et très préférable à un throttle qui retombe sur la flotte
    # réelle. Dupliquer les lignes depuis une seule collecte serait l'autre option —
    # écarté : écrire sous deux locataires depuis une source unique est exactement le
    # motif qui a coûté deux séances de test artiste.
    seen_accounts: dict = {}
    for artist_id, artist_name in artists:
        creds = load_platform_credentials(artist_id, 'meta')
        # Central model: the access_token is admin-owned (META_ACCESS_TOKEN env, shared
        # System User app). The artist supplies only their account_id. Mirror the
        # collector's env fallback here so an account-id-only artist is NOT skipped.
        token = creds.get('access_token') or os.getenv('META_ACCESS_TOKEN')
        if not token or not creds.get('account_id'):
            logger.warning(
                f"Meta not connected for artist_id={artist_id} ({artist_name}) "
                "(no account_id, or shared token missing) — skipping."
            )
            continue

        account = str(creds.get('account_id'))
        if account in seen_accounts:
            logger.warning(
                "Meta: compte %s déjà collecté pour l'artiste %s — reprise sautée "
                "pour %s (id=%s). Ses lignes existantes ne sont pas rafraîchies.",
                account, seen_accounts[account], artist_name, artist_id)
            continue
        seen_accounts[account] = artist_id

        configured += 1
        logger.info(f"▶ Meta API collect — artist_id={artist_id} ({artist_name})")
        try:
            from src.utils.dag_run_logger import DagRunLogger
            run_id = context.get('run_id', '') if context else ''
            full_history = conf.get('full_history', False)
            with DagRunLogger('meta_ads_api_daily', artist_id=artist_id,
                              platform='meta', run_id=run_id) as run_log:
                collector = MetaAdsApiCollector(artist_id=artist_id)
                # `fetch_creatives` fait un appel Graph PAR CRÉATIVE : 143 appels
                # unitaires par locataire et par nuit, mesurés à ~110 s, et le
                # collecteur le documente lui-même comme « le principal moteur de
                # limitation ». Le contenu des créatives (titre, corps, appel à
                # l'action) ne change pas tous les jours ; il se récupère à la demande
                # par un `full_history`.
                total_rows = collector.run(full_history=full_history,
                                           fetch_creatives=full_history)
                run_log.rows_inserted = total_rows or 0
            succeeded += 1
            logger.info(f"  ✅ Done for {artist_name} ({total_rows} insight rows)")
        except Exception as e:
            # Per-artist isolation: a not-shared ad account (Object does not exist /
            # #200 permissions) must NOT poison the other tenants. Surface it loudly
            # per-artist; the task fails below only if EVERY configured artist failed.
            logger.error(f"  ❌ Error for {artist_name}: {safe_error(e)}")
            errors.append(f"{artist_name} (id={artist_id}): {safe_error(e)}")

    if errors:
        logger.warning(f"Meta: {len(errors)} artist(s) failed (isolated, continued): "
                       + " | ".join(errors))

    # Fail only if EVERY configured artist failed (admin-level signal), never on one tenant.
    if configured > 0 and succeeded == 0:
        raise RuntimeError(
            f"Meta API collect failed for all {configured} configured artist(s):\n"
            + "\n".join(errors)
        )


with DAG(
    'meta_ads_api_daily',
    default_args=default_args,
    description='Daily Meta Ads API collection (campaigns, adsets, ads, insights)',
    schedule='0 5 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    dagrun_timeout=dagrun_timeout_for('meta_ads_api_daily'),
    max_active_runs=1,  # concurrent runs hammer the same ad-account → Meta throttle 80004
    tags=['meta', 'ads', 'api'],
) as dag:

    collect_task = PythonOperator(
        task_id='collect_meta_api',
        python_callable=run_meta_api_collector,
    )
