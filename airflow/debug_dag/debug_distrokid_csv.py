"""Debug script for distrokid_csv_watcher DAG — runs locally without Airflow.

Type: Utility
Depends on: DistroKidParser, PostgresHandler, config_loader

Steps:
  1. Environment check (DB config from config.yaml)
  2. DB connectivity + table existence
  3. Parser test — detection + parse for any CSV/TSV in data/raw/distrokid/
  4. Upsert dry-run (shows table + row count, no actual write)

Usage:
    python airflow/debug_dag/debug_distrokid_csv.py
    python airflow/debug_dag/debug_distrokid_csv.py --file path/to/file.tsv
    python airflow/debug_dag/debug_distrokid_csv.py --write   # real upsert + rollup
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
logger = logging.getLogger('debug_distrokid_csv')

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

RAW_DIR = Path(__file__).resolve().parent.parent.parent / 'data' / 'raw' / 'distrokid'

_CONFLICT_COLUMNS = [
    'artist_id', 'isrc', 'title', 'sale_year', 'sale_month',
    'reporting_date', 'store', 'country', 'source_type',
]
_UPDATE_COLUMNS = [
    'quantity', 'earnings_usd', 'songwriter_royalties_usd',
    'recoup_usd', 'team_percentage', 'upc', 'artist_name', 'collected_at',
]


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
        tables = ['distrokid_sales_detail', 'distrokid_monthly_revenue', 'saas_artists']
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
    _section('STEP 2 — Export file scan (*.csv, *.tsv)')
    if override_path:
        p = Path(override_path)
        if not p.exists():
            logger.error(f'File not found: {p}')
            return []
        logger.info(f'Using provided file: {p}')
        return [p]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob('*.csv')) + sorted(RAW_DIR.glob('*.tsv'))
    if not files:
        logger.warning(f'No CSV/TSV files in {RAW_DIR}')
        logger.info('Drop a DistroKid bank-details export into data/raw/distrokid/ and re-run.')
        return []
    logger.info(f'{len(files)} file(s) found:')
    for f in files:
        logger.info(f'  - {f.name} ({f.stat().st_size / 1024:.1f} KB)')
    return files


# ── Step 3: parser test ───────────────────────────────────────────────────────
def step_3_parser_test(files):
    _section('STEP 3 — Parser test (detection + parse)')
    from src.transformers.distrokid_parser import DistroKidParser
    parser = DistroKidParser()
    results = []

    for f in files:
        logger.info(f'\nFile: {f.name}')
        result = parser.parse_file(f, artist_id=1)
        data = result['data']

        if result['type'] is None:
            logger.error('  ❌ Not detected as a DistroKid bank export — check columns')
            continue

        logger.info(f'  ✅ Type: {result["type"]}')
        logger.info(f'  ✅ Rows parsed (after dedup): {len(data)}')

        if data:
            logger.info(f'  Sample row 1 : {data[0]}')
            if len(data) > 1:
                logger.info(f'  Sample row -1: {data[-1]}')
            total_usd = sum(r['earnings_usd'] for r in data)
            months = {(r['sale_year'], r['sale_month']) for r in data}
            logger.info(f'  Total earnings: {total_usd:.2f} USD over {len(months)} month(s)')

        results.append(result)

    return results


# ── Step 4: dry-run ───────────────────────────────────────────────────────────
def step_4_dry_run(parsed_results):
    _section('STEP 4 — Upsert dry-run (no DB write)')
    if not parsed_results:
        logger.info('No parsed data — nothing to show.')
        return

    for result in parsed_results:
        logger.info(f'\n  Source   : {result["source_file"]}')
        logger.info('  Table    : distrokid_sales_detail')
        logger.info(f'  Rows     : {len(result["data"])}')
        logger.info(f'  Conflict : {_CONFLICT_COLUMNS}')
        logger.info(f'  Update   : {_UPDATE_COLUMNS}')

    logger.info('\n  ℹ️  Dry-run complete — no rows were written to the DB.')
    logger.info('  To perform a real import: use the dashboard (page Import CSV)')
    logger.info('  or trigger DAG distrokid_csv_watcher via Airflow UI.')


# ── Step 5: optional real upsert ─────────────────────────────────────────────
def step_5_real_upsert(parsed_results):
    _section('STEP 5 — Real upsert (writes to DB)')
    db = _get_db()
    artist_ids = set()
    try:
        for result in parsed_results:
            data = result['data']
            if not data:
                continue
            n = db.upsert_many(
                table='distrokid_sales_detail',
                data=data,
                conflict_columns=_CONFLICT_COLUMNS,
                update_columns=_UPDATE_COLUMNS,
            )
            logger.info(f'  ✅ distrokid_sales_detail: {n} row(s) upserted')
            artist_ids.update(row['artist_id'] for row in data if row.get('artist_id'))

        # Monthly EUR rollup — same best-effort hook as upload_csv and the DAG.
        for aid in sorted(artist_ids):
            try:
                from src.utils.distrokid_rollup import rollup_sales_to_monthly
                n_months = rollup_sales_to_monthly(db, aid)
                logger.info(f'  ✅ monthly_revenue rolled up: {n_months} month(s) for artist {aid}')
            except Exception as e:
                logger.error(f'  monthly_revenue roll-up failed for artist {aid} (non-blocking): {e}')
    finally:
        db.close()


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Debug DistroKid CSV watcher DAG')
    ap.add_argument('--file', help='Path to a specific CSV/TSV file (optional)')
    ap.add_argument('--write', action='store_true', help='Actually write to DB (default: dry-run only)')
    args = ap.parse_args()

    _section('DEBUG — distrokid_csv_watcher (local run, no Airflow)')
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
