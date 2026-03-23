"""DAG ML — Scoring quotidien des chansons.

Brick 16 : pour chaque artiste actif, calcule les probabilités XGBoost
(DW / RR / Radio) et les forecasts de streams J+7, puis upsert dans
ml_song_predictions.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import logging

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
    'retries': 1,
    'retry_delay': timedelta(minutes=15),
    'on_failure_callback': _on_failure_callback,
}


def run_ml_scoring(**context):
    """Scoring ML pour tous les artistes actifs."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils.credential_loader import get_active_artists
    from src.utils.ml_inference import score_all_songs, MODEL_VERSION
    import os

    db_cfg = {
        'host': os.environ.get('DATABASE_HOST', 'postgres'),
        'port': int(os.environ.get('DATABASE_PORT', 5432)),
        'dbname': os.environ.get('DATABASE_NAME', 'spotify_etl'),
        'user': os.environ.get('DATABASE_USER', 'postgres'),
        'password': os.environ.get('DATABASE_PASSWORD', ''),
    }

    db = PostgresHandler(**db_cfg)
    total_inserted = 0

    try:
        artists = get_active_artists()
        if not artists:
            logger.warning("Aucun artiste actif trouvé — scoring ignoré")
            return

        for artist in artists:
            artist_id = artist['id']
            name = artist.get('name', f'artist_{artist_id}')
            logger.info(f"Scoring ML pour {name!r} (artist_id={artist_id})")

            rows = score_all_songs(db, artist_id)
            if not rows:
                logger.info(f"  → Pas de données pour {name!r}")
                continue

            conflict_cols = ["artist_id", "song", "prediction_date", "model_version"]
            update_cols = [
                "days_since_release", "streams_7d", "streams_28d",
                "dw_probability", "rr_probability", "radio_probability",
                "dw_streams_forecast_7d", "rr_streams_forecast_7d",
                "features_json",
            ]

            db.upsert_many("ml_song_predictions", rows, conflict_cols, update_cols)
            logger.info(f"  → {len(rows)} prédictions upsertées pour {name!r}")
            total_inserted += len(rows)

    finally:
        db.close()

    logger.info(f"Scoring ML terminé — {total_inserted} prédictions au total")


with DAG(
    dag_id='ml_scoring_daily',
    default_args=default_args,
    description='Scoring ML quotidien (XGBoost DW/RR/Radio) pour toutes les chansons actives',
    schedule_interval='0 6 * * *',  # 06h00 UTC, après les DAGs de collecte
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ml', 'scoring'],
) as dag:

    scoring_task = PythonOperator(
        task_id='run_ml_scoring',
        python_callable=run_ml_scoring,
    )
