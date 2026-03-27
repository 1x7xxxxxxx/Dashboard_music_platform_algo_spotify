"""DAG meta_token_refresh — automatic Meta long-lived token renewal.

Runs weekly. For each active artist whose Meta access_token expires within
REFRESH_THRESHOLD_DAYS, exchanges the current token for a new 60-day token
via the official Meta endpoint and persists it to artist_credentials.

Perpetual cycle: each run extends by ~60 days → token never expires as long
as the DAG runs at least once every 60 days (weekly schedule is safe margin).

Requires in artist_credentials (platform='meta'):
  - token_encrypted: contains access_token, app_secret
  - extra_config:    contains app_id
  - expires_at:      populated on first manual save or after first auto-refresh
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

sys.path.insert(0, '/opt/airflow')

import logging
logger = logging.getLogger(__name__)

REFRESH_THRESHOLD_DAYS = 30  # refresh if token expires within this many days


def _failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {e}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _failure_callback,
}


def refresh_meta_tokens(**context):
    """Exchange Meta tokens for all active artists whose token expires soon."""
    import os
    import requests
    from datetime import timezone

    from src.utils.credential_loader import (
        get_active_artists,
        load_platform_credentials,
        update_platform_secret,
        save_platform_credentials,
    )

    artists = get_active_artists()
    if not artists:
        logger.info("No active artists — nothing to refresh.")
        return

    refreshed = []
    skipped = []
    failed = []

    for artist_id, artist_name in artists:
        creds = load_platform_credentials(artist_id, 'meta')
        access_token = creds.get('access_token', '')
        app_id = creds.get('app_id', '')
        app_secret = creds.get('app_secret', '')

        if not access_token:
            skipped.append(f"{artist_name}: no access_token")
            continue
        if not app_id or not app_secret:
            skipped.append(f"{artist_name}: app_id or app_secret missing")
            continue

        # Check expires_at from DB
        import psycopg2
        host = os.getenv('DATABASE_HOST', 'localhost')
        port = int(os.getenv('DATABASE_PORT', 5432))
        try:
            conn = psycopg2.connect(
                host=host, port=port,
                database=os.getenv('DATABASE_NAME', 'spotify_etl'),
                user=os.getenv('DATABASE_USER', 'postgres'),
                password=os.getenv('DATABASE_PASSWORD', ''),
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT expires_at FROM artist_credentials WHERE artist_id = %s AND platform = 'meta'",
                (artist_id,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            failed.append(f"{artist_name}: DB read error — {e}")
            continue

        expires_at = row[0] if row else None
        if expires_at is not None:
            # Make expires_at timezone-naive for comparison
            if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            days_left = (expires_at - datetime.utcnow()).days
            if days_left > REFRESH_THRESHOLD_DAYS:
                skipped.append(f"{artist_name}: {days_left} days left — no refresh needed")
                continue
            logger.info(f"{artist_name}: token expires in {days_left} day(s) — refreshing.")
        else:
            # No expires_at recorded — refresh unconditionally to populate it
            logger.info(f"{artist_name}: expires_at not set — refreshing to populate.")

        # Call Meta token exchange endpoint
        try:
            r = requests.get(
                'https://graph.facebook.com/v18.0/oauth/access_token',
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': app_id,
                    'client_secret': app_secret,
                    'fb_exchange_token': access_token,
                },
                timeout=15,
            )
            data = r.json()

            if r.status_code != 200 or 'access_token' not in data:
                err = data.get('error', data)
                failed.append(f"{artist_name}: Meta API error — {err}")
                continue

            new_token = data['access_token']
            expires_in = data.get('expires_in', 5184000)  # default 60 days
            new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            update_platform_secret(
                artist_id, 'meta', 'access_token', new_token,
                expires_at=new_expires_at,
            )
            refreshed.append(
                f"{artist_name}: new token saved, expires {new_expires_at.strftime('%Y-%m-%d')} "
                f"(+{expires_in // 86400} days)"
            )

        except Exception as e:
            failed.append(f"{artist_name}: refresh exception — {e}")

    # Summary log
    logger.info(f"Meta token refresh summary — {len(artists)} artist(s) processed:")
    for msg in refreshed:
        logger.info(f"  ✅ {msg}")
    for msg in skipped:
        logger.info(f"  ⏭ {msg}")
    for msg in failed:
        logger.error(f"  ❌ {msg}")

    if failed:
        raise RuntimeError(
            f"Meta token refresh failed for {len(failed)} artist(s): "
            + "; ".join(failed)
        )


with DAG(
    'meta_token_refresh',
    default_args=default_args,
    description='Weekly automatic renewal of Meta long-lived access tokens',
    schedule_interval='0 7 * * 1',  # every Monday at 07:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['meta', 'instagram', 'credentials'],
) as dag:

    refresh_task = PythonOperator(
        task_id='refresh_meta_tokens',
        python_callable=refresh_meta_tokens,
        provide_context=True,
    )
