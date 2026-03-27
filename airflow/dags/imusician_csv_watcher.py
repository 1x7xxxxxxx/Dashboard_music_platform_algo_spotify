"""DAG iMusician CSV Watcher — ingestion of iMusician CSV exports.

Type: Feature
Depends on: IMusicianCSVParser, PostgresHandler
Persists in: imusician_release_summary, imusician_sales_detail

Schedule: every 15 minutes.
Watch dir : /opt/airflow/data/raw/imusician/
Archive dir: /opt/airflow/data/processed/imusician/

Auto-detects CSV type (release_summary / sales_detail) and upserts into the
corresponding table. artist_id is read from dag_run.conf (defaults to 1).
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator

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


# ─────────────────────────────────────────────
# Tasks
# ─────────────────────────────────────────────

def check_for_new_csv(**context):
    """Scan watch dir; return branch name."""
    raw_dir = Path('/opt/airflow/data/raw/imusician')
    raw_dir.mkdir(parents=True, exist_ok=True)

    csv_files = list(raw_dir.glob('*.csv'))
    logger.info(f"Scan {raw_dir}: {len(csv_files)} CSV file(s) found")

    if csv_files:
        context['task_instance'].xcom_push(
            key='csv_files', value=[str(f) for f in csv_files]
        )
        return 'process_csv_files'
    return 'skip_processing'


def process_csv_files(**context):
    """Parse each CSV and upsert into the matching table."""
    from src.database.postgres_handler import PostgresHandler
    from src.transformers.imusician_csv_parser import IMusicianCSVParser

    csv_files = context['task_instance'].xcom_pull(
        task_ids='check_new_csv', key='csv_files'
    ) or []

    if not csv_files:
        logger.info("No files to process.")
        return 0

    conf = (context.get('dag_run').conf or {})
    artist_id = int(conf.get('artist_id', 1))

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )

    parser = IMusicianCSVParser()
    archive_dir = Path('/opt/airflow/data/processed/imusician')
    archive_dir.mkdir(parents=True, exist_ok=True)

    processed = 0

    for path_str in csv_files:
        csv_file = Path(path_str)
        if not csv_file.exists():
            continue

        logger.info(f"Processing: {csv_file.name}")
        result = parser.parse_csv_file(csv_file, artist_id=artist_id)
        csv_type = result['type']
        data = result['data']

        if not data or csv_type is None:
            logger.warning(f"No data or unknown type for {csv_file.name} — skipping")
            continue

        try:
            if csv_type == 'release_summary':
                n = db.upsert_many(
                    table='imusician_release_summary',
                    data=data,
                    conflict_columns=['artist_id', 'barcode', 'year', 'month'],
                    update_columns=[
                        'release_title', 'track_downloads', 'track_streams',
                        'release_downloads', 'track_downloads_revenue',
                        'track_streams_revenue', 'release_downloads_revenue',
                        'total_revenue', 'collected_at',
                    ],
                )
                logger.info(f"  release_summary upserted: {n} row(s)")

            elif csv_type == 'sales_detail':
                n = db.upsert_many(
                    table='imusician_sales_detail',
                    data=data,
                    conflict_columns=[
                        'artist_id', 'isrc', 'sales_year', 'sales_month',
                        'statement_year', 'statement_month', 'shop', 'country',
                        'transaction_type',
                    ],
                    update_columns=['quantity', 'revenue_eur', 'collected_at'],
                )
                logger.info(f"  sales_detail upserted: {n} row(s)")

            # Archive
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_file.rename(archive_dir / f"{csv_file.stem}_{ts}{csv_file.suffix}")
            logger.info(f"  Archived: {csv_file.stem}_{ts}{csv_file.suffix}")
            processed += 1

        except Exception as e:
            logger.error(f"Error on {csv_file.name}: {e}")
            continue

    db.close()
    logger.info(f"Done. {processed}/{len(csv_files)} file(s) processed.")
    return processed


# ─────────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────────

with DAG(
    dag_id='imusician_csv_watcher',
    default_args=default_args,
    description='iMusician CSV ingestion (release summary + sales detail)',
    schedule_interval='*/15 * * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['imusician', 'csv', 'production'],
    max_active_runs=1,
) as dag:

    check_task = BranchPythonOperator(
        task_id='check_new_csv',
        python_callable=check_for_new_csv,
        provide_context=True,
    )

    process_task = PythonOperator(
        task_id='process_csv_files',
        python_callable=process_csv_files,
        provide_context=True,
    )

    skip_task = EmptyOperator(task_id='skip_processing')
    end_task = EmptyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

    check_task >> [process_task, skip_task]
    process_task >> end_task
    skip_task >> end_task
