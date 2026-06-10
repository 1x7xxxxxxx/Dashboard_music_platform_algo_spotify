"""DAG DistroKid CSV Watcher — ingestion of DistroKid bank-details exports.

Type: Feature
Depends on: DistroKidParser, PostgresHandler
Persists in: distrokid_sales_detail, distrokid_monthly_revenue (rollup)

Schedule: every 15 minutes.
Watch dir : /opt/airflow/data/raw/distrokid/   (*.csv and *.tsv)
Archive dir: /opt/airflow/data/processed/distrokid/

Amounts are USD; the monthly rollup converts to EUR with DISTROKID_USD_EUR_RATE
(default 0.92). artist_id is read from dag_run.conf (defaults to 1).
Format reference: .claude/dev-docs/distrokid-export-format.md.
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

_CONFLICT_COLUMNS = [
    'artist_id', 'isrc', 'title', 'sale_year', 'sale_month',
    'reporting_date', 'store', 'country', 'source_type',
]
_UPDATE_COLUMNS = [
    'quantity', 'earnings_usd', 'songwriter_royalties_usd',
    'recoup_usd', 'team_percentage', 'upc', 'artist_name', 'collected_at',
]


# ─────────────────────────────────────────────
# Tasks
# ─────────────────────────────────────────────

def check_for_new_csv(**context):
    """Scan watch dir; return branch name."""
    raw_dir = Path('/opt/airflow/data/raw/distrokid')
    raw_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(raw_dir.glob('*.csv')) + sorted(raw_dir.glob('*.tsv'))
    logger.info(f"Scan {raw_dir}: {len(files)} file(s) found")

    if files:
        context['task_instance'].xcom_push(
            key='csv_files', value=[str(f) for f in files]
        )
        return 'process_csv_files'
    return 'skip_processing'


def process_csv_files(**context):
    """Parse each export and upsert into distrokid_sales_detail."""
    from src.database.postgres_handler import PostgresHandler
    from src.transformers.distrokid_parser import DistroKidParser

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

    parser = DistroKidParser()
    archive_dir = Path('/opt/airflow/data/processed/distrokid')
    archive_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    sales_imported = False

    for path_str in csv_files:
        csv_file = Path(path_str)
        if not csv_file.exists():
            continue

        logger.info(f"Processing: {csv_file.name}")
        result = parser.parse_file(csv_file, artist_id=artist_id)
        data = result['data']

        if not data or result['type'] is None:
            logger.warning(f"No data or unknown type for {csv_file.name} — skipping")
            continue

        try:
            n = db.upsert_many(
                table='distrokid_sales_detail',
                data=data,
                conflict_columns=_CONFLICT_COLUMNS,
                update_columns=_UPDATE_COLUMNS,
            )
            logger.info(f"  distrokid_sales_detail upserted: {n} row(s)")
            sales_imported = True

            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_file.rename(archive_dir / f"{csv_file.stem}_{ts}{csv_file.suffix}")
            logger.info(f"  Archived: {csv_file.stem}_{ts}{csv_file.suffix}")
            processed += 1

        except Exception as e:
            logger.error(f"Error on {csv_file.name}: {e}")
            continue

    # Roll USD detail up into monthly EUR revenue (Distributeur + ROI read it).
    # Best-effort: a roll-up failure must not fail the import. Same hook as upload_csv.
    if sales_imported:
        try:
            from src.utils.distrokid_rollup import rollup_sales_to_monthly
            n_months = rollup_sales_to_monthly(db, artist_id)
            logger.info(f"  monthly_revenue rolled up: {n_months} month(s) for artist {artist_id}")
        except Exception as e:
            logger.error(f"monthly_revenue roll-up failed (non-blocking): {e}")

    db.close()
    logger.info(f"Done. {processed}/{len(csv_files)} file(s) processed.")
    return processed


# ─────────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────────

with DAG(
    dag_id='distrokid_csv_watcher',
    default_args=default_args,
    description='DistroKid bank-details ingestion (sales detail + monthly EUR rollup)',
    schedule_interval='*/15 * * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['distrokid', 'csv', 'production'],
    max_active_runs=1,
) as dag:

    check_task = BranchPythonOperator(
        task_id='check_new_csv',
        python_callable=check_for_new_csv,
    )

    process_task = PythonOperator(
        task_id='process_csv_files',
        python_callable=process_csv_files,
    )

    skip_task = EmptyOperator(task_id='skip_processing')
    end_task = EmptyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

    check_task >> [process_task, skip_task]
    process_task >> end_task
    skip_task >> end_task
