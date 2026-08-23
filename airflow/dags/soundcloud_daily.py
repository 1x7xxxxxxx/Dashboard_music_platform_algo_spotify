"""DAG SoundCloud — collecte journalière des stats.

Brick 6 : supporte artist_id dans dag_run.conf.
  - conf.artist_id fourni → collecte pour cet artiste uniquement (credentials depuis DB).
  - conf absent           → fallback sur env vars (comportement historique, artist_id=1).
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

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


def precheck_soundcloud_credentials(**context):
    """Informational pre-check — never fails the fleet.

    Central-app model: client_id/client_secret are admin-owned (shared env app); the
    artist supplies only their user_id. An artist without a user_id simply hasn't
    connected SoundCloud and must be SKIPPED, not block every other tenant. The actual
    fail-if-all-failed decision lives in the collector (per-artist isolation).
    """
    from src.utils.credential_loader import get_active_artists, load_platform_credentials

    app_client_id = os.getenv('SOUNDCLOUD_CLIENT_ID')
    app_client_secret = os.getenv('SOUNDCLOUD_CLIENT_SECRET')

    artists = get_active_artists()
    if not artists:
        logger.info("No active artists — skipping credential pre-check.")
        return

    configured, blocked = [], []
    for aid, name in artists:
        creds = load_platform_credentials(aid, 'soundcloud')
        user_id = creds.get('user_id')
        client_id = creds.get('client_id') or app_client_id
        client_secret = creds.get('client_secret') or app_client_secret
        if not user_id:
            continue  # not connected — skip silently
        if client_id and client_secret:
            configured.append(name)
        else:
            blocked.append(f"{name} (id={aid})")

    if blocked:
        logger.warning(
            "SoundCloud shared app not configured (SOUNDCLOUD_CLIENT_ID/SECRET) for "
            f"artists with a user_id: {', '.join(blocked)} — admin action required."
        )
    logger.info(f"✅ SoundCloud config OK for {len(configured)}/{len(artists)} artist(s) "
                f"(skipped {len(artists) - len(configured) - len(blocked)} not-connected).")


def run_soundcloud_collector(**context):
    import logging
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    from src.utils.credential_loader import load_platform_credentials, get_active_artists

    logger = logging.getLogger(__name__)

    # ── Résolution de l'artiste ────────────────────────────────────────
    conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
    artist_id_conf = conf.get('artist_id')

    artists = get_active_artists(include_artist_id=artist_id_conf)

    if not artists:
        # An empty list now means EXACTLY one thing (credential_loader raises on a
        # read failure and on an unknown artist_id): the deployment has no active
        # tenant. The legacy single-tenant fallback borrowed the admin's env
        # identity, so it is opt-in and explicit — never a silent default.
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
        # ── Credentials depuis DB, fallback env vars (app partagée) ────
        creds = load_platform_credentials(artist_id, 'soundcloud')
        # App credentials (admin-owned, shared by every tenant): env fallback is the
        # central-app model (ADR-006) and stays.
        client_id     = creds.get('client_id')     or os.getenv('SOUNDCLOUD_CLIENT_ID')
        client_secret = creds.get('client_secret') or os.getenv('SOUNDCLOUD_CLIENT_SECRET')
        refresh_token = creds.get('refresh_token') or os.getenv('SOUNDCLOUD_REFRESH_TOKEN')
        # TENANT IDENTITY: no fallback, ever. SOUNDCLOUD_USER_ID holds the ADMIN's
        # profile, so falling back on it collected the admin's tracks and wrote them
        # under this artist's artist_id — what the two beta testers actually saw.
        # An empty string is an absence: the credentials form can persist "" when an
        # artist saves the tab without filling it in.
        user_id       = (creds.get('user_id') or '').strip()

        # Every branch below leaves a row in etl_run_log. Absence of a row is what made
        # that ledger unable to answer "did collection run for this tenant?" — a
        # question no other surface can answer, and the reason a tenant can stop
        # collecting for nights without anything saying so.
        if not user_id:
            # Un artiste signé sur un label n'a pas de profil personnel, et n'en aura
            # jamais : ses sorties paraissent sous le compte du label. L'unité
            # collectable est alors le TITRE — `GET /tracks/{id}` rend ses écoutes quel
            # que soit le compte qui l'héberge. Sauter ici revenait à exiger la seule
            # chose qu'il ne peut pas fournir, et le trou était invisible : la fonction
            # de déclaration existait, fonctionnait, et n'était jamais atteinte pour lui.
            # Mesuré sur le cas GRiNCH le 2026-08-23.
            from src.utils.claimed_tracks import has_claimed_tracks
            if not has_claimed_tracks(artist_id, 'soundcloud'):
                logger.info(f"  {artist_name} (id={artist_id}) sans user_id SoundCloud "
                            f"ni titre déclaré — skip")
                record_tenant_skip('soundcloud_daily', artist_id, 'soundcloud',
                                   'no SoundCloud user_id and no claimed track', run_id)
                continue
            logger.info("  %s (id=%s) sans profil SoundCloud, mais des titres déclarés "
                        "— collecte des seules déclarations", artist_name, artist_id)
        if not client_id or not client_secret:
            logger.warning(f"  {artist_name} (id={artist_id}) — app SoundCloud partagée non "
                           "configurée (SOUNDCLOUD_CLIENT_ID/SECRET) — contacter admin ; skip")
            per_artist_errors.append((artist_id, artist_name, "app credentials missing (admin)"))
            record_tenant_skip('soundcloud_daily', artist_id, 'soundcloud',
                               'shared SoundCloud app not configured (admin action)', run_id)
            continue

        configured += 1
        logger.info(f"▶ SoundCloud collect — artist_id={artist_id} ({artist_name})")
        try:
            collector = SoundCloudCollector(
                artist_id=artist_id,
                client_id=client_id,
                client_secret=client_secret,
                user_id=user_id,
                refresh_token=refresh_token,
            )
            rows = collector.run() or 0
            record_tenant_success('soundcloud_daily', artist_id, 'soundcloud', rows, run_id)
            succeeded += 1
            logger.info(f"  ✅ Collecte terminée pour {artist_name}")
        except Exception as e:
            # Per-artist isolation: the collector still raises (rule #6); the loop
            # absorbs it per-tenant so a single failure can't blank the others.
            logger.error(f"  ❌ Erreur pour {artist_name} : {safe_error(e)}")
            per_artist_errors.append((artist_id, artist_name, safe_error(e)[:200]))
            record_tenant_failure('soundcloud_daily', artist_id, 'soundcloud', e, run_id)
            continue

    if per_artist_errors:
        summary = '; '.join(f'{aid}/{name}: {err}' for aid, name, err in per_artist_errors)
        logger.warning(f"SoundCloud: {len(per_artist_errors)} artiste(s) en échec (isolés) : {summary}")

    # Fail the task only if EVERY configured artist failed (admin-level signal),
    # never on a single bad tenant.
    if configured > 0 and succeeded == 0:
        raise ValueError(
            "SoundCloud collection failed for every configured artist: "
            + '; '.join(f'{aid}/{name}: {err}' for aid, name, err in per_artist_errors)
        )


with DAG(
    'soundcloud_daily',
    default_args=default_args,
    description='Collecte journalière des stats SoundCloud',
    schedule_interval='0 9 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,  # serialize external-API collection to avoid rate limits
    tags=['social', 'soundcloud'],
) as dag:

    precheck_task = PythonOperator(
        task_id='precheck_credentials',
        python_callable=precheck_soundcloud_credentials,
    )

    collect_task = PythonOperator(
        task_id='collect_soundcloud_stats',
        python_callable=run_soundcloud_collector,
    )

    precheck_task >> collect_task
