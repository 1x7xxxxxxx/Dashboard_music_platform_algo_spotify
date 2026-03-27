"""Debug script for imusician_csv_watcher DAG — runs locally without Airflow.

Type: Utility
Depends on: IMusicianCSVParser, PostgresHandler, config_loader

Steps:
  1. Environment check (DB config from config.yaml)
  2. DB connectivity + table existence
  3. Parser test — type detection + parse for any CSV in data/raw/imusician/
  4. Upsert dry-run (shows SQL + row count, no actual write)

Usage:
    python airflow/debug_dag/debug_imusician_csv.py
    python airflow/debug_dag/debug_imusician_csv.py --file path/to/file.csv
"""
import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
)
logger = logging.getLogger('debug_imusician_csv')

# ── Load DB config ────────────────────────────────────────────────────────────
try:
    from src.utils.config_loader import config_loader
    _cfg = config_loader.load()
    _db_cfg = _cfg.get('database', {})
    os.environ.setdefault('DATABASE_HOST',     str(_db_cfg.get('host',     'localhost')))
    os.environ.setdefault('DATABASE_PORT',     str(_db_cfg.get('port',     5433)))
    os.environ.setdefault('DATABASE_NAME',     str(_db_cfg.get('database', 'spotify_etl')))
    os.environ.setdefault('DATABASE_USER',     str(_db_cfg.get('user',     'postgres')))
    os.environ.setdefault('DATABASE_PASSWORD', str(_db_cfg.get('password', '')))
    logger.info('DB config loaded from config.yaml')
except Exception as e:
    logger.warning(f'config.yaml unavailable — relying on .env: {e}')

RAW_DIR = Path(__file__).resolve().parent.parent.parent / 'data' / 'raw' / 'imusician'


def _get_db():
    from src.database.postgres_handler import PostgresHandler
    return PostgresHandler(
        host=os.environ['DATABASE_HOST'],
        port=int(os.environ['DATABASE_PORT']),
        database=os.environ['DATABASE_NAME'],
        user=os.environ['DATABASE_USER'],
        password=os.environ['DATABASE_PASSWORD'],
    )


def _section(title):
    print(f'\n{"=" * 70}')
    print(f'  {title}')
    print('=' * 70)


# ── Step 1: DB connectivity ───────────────────────────────────────────────────
def step_1_check_db():
    _section('STEP 1 — PostgreSQL connectivity + table existence')
    try:
        db = _get_db()
        tables = ['imusician_release_summary', 'imusician_sales_detail', 'saas_artists']
        for t in tables:
            try:
                row = db.fetch_query(f'SELECT COUNT(*) FROM {t}')
                logger.info(f'  ✅ {t}: {row[0][0]} rows')
            except Exception as e:
                logger.warning(f'  ⚠️  {t}: {e}')
        db.close()
        return True
    except Exception as e:
        logger.error(f'❌ DB connection failed: {e}')
        return False


# ── Step 2: scan files ────────────────────────────────────────────────────────
def step_2_scan_files(override_path=None):
    _section('STEP 2 — CSV file scan')
    if override_path:
        p = Path(override_path)
        if not p.exists():
            logger.error(f'File not found: {p}')
            return []
        logger.info(f'Using provided file: {p}')
        return [p]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = list(RAW_DIR.glob('*.csv'))
    if not files:
        logger.warning(f'No CSV files in {RAW_DIR}')
        logger.info('Drop an iMusician CSV export into data/raw/imusician/ and re-run.')
        return []
    logger.info(f'{len(files)} file(s) found:')
    for f in files:
        logger.info(f'  - {f.name} ({f.stat().st_size / 1024:.1f} KB)')
    return files


# ── Step 3: parser test ───────────────────────────────────────────────────────
def step_3_parser_test(files):
    _section('STEP 3 — Parser test (type detection + parse)')
    from src.transformers.imusician_csv_parser import IMusicianCSVParser
    parser = IMusicianCSVParser()
    results = []

    for f in files:
        logger.info(f'\nFile: {f.name}')
        result = parser.parse_csv_file(f, artist_id=1)
        csv_type = result['type']
        data = result['data']

        if csv_type is None:
            logger.error('  ❌ Type not detected — check column names')
            continue

        logger.info(f'  ✅ Type: {csv_type}')
        logger.info(f'  ✅ Rows parsed: {len(data)}')

        if data:
            logger.info(f'  Sample row 1 : {data[0]}')
            if len(data) > 1:
                logger.info(f'  Sample row -1: {data[-1]}')

        results.append(result)

    return results


# ── Step 4: dry-run ───────────────────────────────────────────────────────────
def step_4_dry_run(parsed_results):
    _section('STEP 4 — Upsert dry-run (no DB write)')
    if not parsed_results:
        logger.info('No parsed data — nothing to show.')
        return

    for result in parsed_results:
        csv_type = result['type']
        data = result['data']
        source = result['source_file']

        if csv_type == 'release_summary':
            table = 'imusician_release_summary'
            conflict = ['artist_id', 'barcode', 'year', 'month']
            update = ['release_title', 'track_downloads', 'track_streams', 'total_revenue', 'collected_at']
        else:
            table = 'imusician_sales_detail'
            conflict = ['artist_id', 'isrc', 'sales_year', 'sales_month',
                        'statement_year', 'statement_month', 'shop', 'country', 'transaction_type']
            update = ['quantity', 'revenue_eur', 'collected_at']

        logger.info(f'\n  Source   : {source}')
        logger.info(f'  Type     : {csv_type}')
        logger.info(f'  Table    : {table}')
        logger.info(f'  Rows     : {len(data)}')
        logger.info(f'  Conflict : {conflict}')
        logger.info(f'  Update   : {update}')

        if data:
            years = set()
            months = set()
            for row in data:
                y = row.get('year') or row.get('sales_year')
                m = row.get('month') or row.get('sales_month')
                if y:
                    years.add(y)
                if m:
                    months.add(m)
            if years:
                logger.info(f'  Years    : {sorted(years)}')
            if months:
                logger.info(f'  Months   : {sorted(months)}')

    logger.info('\n  ℹ️  Dry-run complete — no rows were written to the DB.')
    logger.info('  To perform a real import: use the dashboard (Distributeur → Import CSV)')
    logger.info('  or trigger DAG imusician_csv_watcher via Airflow UI.')


# ── Step 5: optional real upsert ─────────────────────────────────────────────
def step_5_real_upsert(parsed_results):
    _section('STEP 5 — Real upsert (writes to DB)')
    db = _get_db()
    try:
        for result in parsed_results:
            csv_type = result['type']
            data = result['data']
            if not data:
                continue

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
                logger.info(f'  ✅ release_summary: {n} row(s) upserted')

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
                logger.info(f'  ✅ sales_detail: {n} row(s) upserted')
    finally:
        db.close()


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Debug iMusician CSV watcher DAG')
    ap.add_argument('--file', help='Path to a specific CSV file (optional)')
    ap.add_argument('--write', action='store_true', help='Actually write to DB (default: dry-run only)')
    args = ap.parse_args()

    _section('DEBUG — imusician_csv_watcher (local run, no Airflow)')
    logger.info(
        f"DB: {os.environ.get('DATABASE_HOST')}:{os.environ.get('DATABASE_PORT')}"
        f"/{os.environ.get('DATABASE_NAME')}"
    )

    if not step_1_check_db():
        logger.error('DB unreachable — stopping. Check Docker: docker-compose up -d')
        sys.exit(1)

    files = step_2_scan_files(override_path=args.file)
    if not files:
        sys.exit(0)

    parsed = step_3_parser_test(files)

    if args.write and parsed:
        step_5_real_upsert(parsed)
    else:
        step_4_dry_run(parsed)

    _section('DONE')
