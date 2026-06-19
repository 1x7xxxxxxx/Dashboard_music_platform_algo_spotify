"""DAG ML — Outcome labelling (weekly).

Type: Feature
Depends on: ml_outcome_labeling.label_predictions, PostgresHandler, get_active_artists
Persists in: ml_prediction_outcomes

For each active artist, pairs every still-unlabelled ml_song_predictions row that is
old enough (>= 28 days) with the realized DW/RR/Radio 28-day streams manually captured
in s4a_song_algo_outcomes (Saisie S4A), bins them to 0/1 training labels, and upserts
into ml_prediction_outcomes. Idempotent — only new labels are written each run.

Weekly (Monday 06:00 UTC, after the daily scoring has long settled). The pairs
accumulate the live training set for the future champion/challenger retraining loop.
"""
import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, '/opt/airflow')

logger = logging.getLogger(__name__)


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {e}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}


def run_outcome_labeling(**context):
    """Label old-enough predictions for every active artist."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils.credential_loader import get_active_artists
    from src.utils.ml_outcome_labeling import label_predictions

    db = PostgresHandler(
        host=os.environ.get('DATABASE_HOST', 'postgres'),
        port=int(os.environ.get('DATABASE_PORT', 5432)),
        database=os.environ.get('DATABASE_NAME', 'spotify_etl'),
        user=os.environ.get('DATABASE_USER', 'postgres'),
        password=os.environ.get('DATABASE_PASSWORD', ''),
    )
    total = 0
    try:
        artists = get_active_artists()
        if not artists:
            logger.warning("Aucun artiste actif — outcome labelling ignoré")
            return
        per_artist_errors = []  # multi-tenant isolation — one bad tenant must not abort labelling
        for artist_id, name in artists:
            try:
                n = label_predictions(db, artist_id)
                logger.info(f"  → {n} prédiction(s) labellisée(s) pour {name!r} (artist_id={artist_id})")
                total += n
            except Exception as e:
                logger.error(f"  → Labelling failed for {name!r} (artist_id={artist_id}): {e}")
                per_artist_errors.append((artist_id, name, str(e)[:200]))
                continue

        if per_artist_errors and total == 0:
            raise RuntimeError(
                "Outcome labelling failed for every artist: "
                + "; ".join(f"{aid}/{n}: {err}" for aid, n, err in per_artist_errors)
            )
    finally:
        db.close()
    logger.info(f"Outcome labelling terminé — {total} nouveau(x) label(s) au total")


with DAG(
    dag_id='ml_outcome_labeling',
    default_args=default_args,
    description='Labellisation hebdo des prédictions ML avec les outcomes DW/RR/Radio réalisés',
    schedule_interval='0 6 * * 1',  # Monday 06:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['ml', 'labeling'],
) as dag:

    label_task = PythonOperator(
        task_id='run_outcome_labeling',
        python_callable=run_outcome_labeling,
    )
