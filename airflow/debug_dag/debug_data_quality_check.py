"""Debug script for data_quality_check DAG — runs locally without Airflow.

Reimplements all 4 task checks inline (no Airflow import, Windows-compatible).
Tasks mirrored:
  1. check_meta_ads_freshness   — Meta Ads data < 48h
  2. check_spotify_consistency  — 5 quality checks on S4A/Spotify tables
  3. generate_daily_stats       — cross-source KPI snapshot
  4. send_summary_notification  — skipped locally (no XCom, no SMTP required)

Usage:
    python airflow/debug_dag/debug_data_quality_check.py
"""
import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
)
logger = logging.getLogger('debug_data_quality_check')

# ── Load DB config from config.yaml ──────────────────────────────────────────
try:
    from src.utils.config_loader import config_loader
    _cfg = config_loader.load()
    _db = _cfg.get('database', {})
    os.environ.setdefault('DATABASE_HOST', str(_db.get('host', 'localhost')))
    os.environ.setdefault('DATABASE_PORT', str(_db.get('port', 5433)))
    os.environ.setdefault('DATABASE_NAME', str(_db.get('database', 'spotify_etl')))
    os.environ.setdefault('DATABASE_USER', str(_db.get('user', 'postgres')))
    os.environ.setdefault('DATABASE_PASSWORD', str(_db.get('password', '')))
    logger.info('DB config loaded from config.yaml')
except Exception as e:
    logger.warning(f'config.yaml unavailable — relying on .env: {e}')


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
    _section('STEP 1 — PostgreSQL connectivity')
    try:
        db = _get_db()
        tables = [
            'meta_campaigns', 'meta_insights',
            's4a_song_timeline', 's4a_songs_global', 's4a_audience',
            'saas_artists',
        ]
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


# ── Step 2: check_meta_ads_freshness ─────────────────────────────────────────
def step_2_meta_freshness():
    _section('STEP 2 — check_meta_ads_freshness')
    db = _get_db()
    try:
        result = db.fetch_query("""
            SELECT
                MAX(collected_at) as last_collection,
                EXTRACT(EPOCH FROM (NOW() - MAX(collected_at))) / 3600 as hours_ago
            FROM meta_campaigns
        """)
        if not result or not result[0][0]:
            logger.error('❌ No Meta Ads data found in DB')
            return False
        last_collection, hours_ago = result[0]
        logger.info(f'Last collection: {last_collection}')
        logger.info(f'Hours ago: {hours_ago:.1f}h (threshold: 48h)')
        if hours_ago > 48:
            logger.error(f'❌ Data stale: {hours_ago:.1f}h > 48h')
            return False
        active = db.fetch_query("SELECT COUNT(*) FROM meta_campaigns WHERE status = 'ACTIVE'")[0][0]
        logger.info(f'✅ {active} active campaign(s) — data is fresh')
        return True
    except Exception as e:
        logger.error(f'Task failed: {e}')
        return False
    finally:
        db.close()


# ── Step 3: check_spotify_data_consistency ────────────────────────────────────
def step_3_spotify_consistency():
    _section('STEP 3 — check_spotify_data_consistency')
    db = _get_db()
    issues = []
    warnings = []
    try:
        # Check 1: artists without S4A data
        orphans = db.fetch_query("""
            SELECT a.id, a.name FROM saas_artists a
            WHERE a.active = TRUE
              AND NOT EXISTS (SELECT 1 FROM s4a_song_timeline t WHERE t.artist_id = a.id)
        """)
        if orphans:
            warnings.append(f'{len(orphans)} active artist(s) without S4A data')
            for aid, name in orphans:
                logger.warning(f'  ⚠️  {name} (id={aid}) has no S4A data')
        else:
            logger.info('✅ Check 1: all active artists have S4A data')

        # Check 2: timeline vs songs_global consistency
        missing = db.fetch_query("""
            SELECT DISTINCT song FROM s4a_song_timeline
            WHERE song NOT IN (SELECT song FROM s4a_songs_global)
            LIMIT 10
        """)
        if missing:
            warnings.append(f'{len(missing)} song(s) in timeline but not in songs_global')
            logger.warning(f'  ⚠️  {len(missing)} songs missing from songs_global')
        else:
            logger.info('✅ Check 2: timeline/songs_global consistency OK')

        # Check 3: suspiciously high stream values
        suspicious = db.fetch_query("""
            SELECT song, date, streams FROM s4a_song_timeline
            WHERE streams > 1000000 ORDER BY streams DESC LIMIT 5
        """)
        if suspicious:
            warnings.append(f'{len(suspicious)} day(s) with >1M streams')
            for song, date, streams in suspicious:
                logger.warning(f'  ⚠️  {song} on {date}: {streams:,} streams')
        else:
            logger.info('✅ Check 3: no anomalous stream values')

        # Check 4: songs with very few data points
        gaps = db.fetch_query("""
            SELECT song, COUNT(*) as days_count FROM s4a_song_timeline
            GROUP BY song HAVING COUNT(*) < 7 ORDER BY days_count ASC LIMIT 10
        """)
        if gaps:
            warnings.append(f'{len(gaps)} song(s) with fewer than 7 days of data')
            for song, days in gaps[:5]:
                logger.warning(f'  ⚠️  {song}: {days} day(s)')
        else:
            logger.info('✅ Check 4: all songs have sufficient data points')

        # Check 5: duplicate rows in timeline
        dupes = db.fetch_query("""
            SELECT song, date, COUNT(*) FROM s4a_song_timeline
            GROUP BY song, date HAVING COUNT(*) > 1 LIMIT 5
        """)
        if dupes:
            issues.append(f'{len(dupes)} duplicate(s) in s4a_song_timeline')
            for song, date, count in dupes:
                logger.error(f'  ❌ {song} on {date}: {count} entries')
        else:
            logger.info('✅ Check 5: no duplicates in timeline')

        logger.info(f'\nSummary: {len(issues)} issue(s), {len(warnings)} warning(s)')
        for w in warnings:
            logger.warning(f'  ⚠️  {w}')
        for e in issues:
            logger.error(f'  ❌ {e}')
        return len(issues) == 0
    except Exception as e:
        logger.error(f'Task failed: {e}')
        return False
    finally:
        db.close()


# ── Step 4: generate_daily_stats ─────────────────────────────────────────────
def step_4_daily_stats():
    _section('STEP 4 — generate_daily_stats')
    db = _get_db()
    try:
        # Meta Ads last 24h
        meta = db.fetch_query("""
            SELECT COUNT(DISTINCT ad_id), COALESCE(SUM(impressions),0),
                   COALESCE(SUM(clicks),0), COALESCE(SUM(spend),0)
            FROM meta_insights WHERE date >= CURRENT_DATE - INTERVAL '1 day'
        """)[0]
        logger.info(f'Meta Ads (24h): ads={meta[0]}, impressions={meta[1]:,}, '
                    f'clicks={meta[2]:,}, spend={float(meta[3]):.2f}€')

        # Artists
        artists = db.fetch_query("SELECT COUNT(*) FROM saas_artists WHERE active = TRUE")[0][0]
        logger.info(f'Active artists: {artists}')

        # S4A tracks
        tracks = db.fetch_query(
            "SELECT COUNT(DISTINCT song) FROM s4a_song_timeline "
            "WHERE song NOT ILIKE '%1x7xxxxxxx%'"
        )[0][0]
        logger.info(f'Tracked songs (S4A): {tracks}')

        # S4A audience last 24h
        s4a = db.fetch_query("""
            SELECT COALESCE(SUM(streams),0), COALESCE(SUM(listeners),0),
                   COALESCE(MAX(followers),0)
            FROM s4a_audience WHERE date >= CURRENT_DATE - INTERVAL '1 day'
        """)[0]
        logger.info(f'S4A (24h): streams={int(s4a[0]):,}, listeners={int(s4a[1]):,}, '
                    f'followers={int(s4a[2]):,}')

        logger.info('✅ Daily stats generated')
        return True
    except Exception as e:
        logger.error(f'Task failed: {e}')
        return False
    finally:
        db.close()


# ── Step 5: send_summary_notification ────────────────────────────────────────
def step_5_summary():
    _section('STEP 5 — send_summary_notification')
    smtp = os.environ.get('SMTP_USER') or os.environ.get('SMTP_HOST')
    if not smtp:
        logger.info('SMTP not configured — email skipped (expected locally)')
        return True
    try:
        from src.utils.email_alerts import EmailAlert
        EmailAlert().send_alert(
            f'[DEBUG] Daily summary — {datetime.now().strftime("%Y-%m-%d")}',
            '<p>Debug test from debug_data_quality_check.py</p>',
        )
        logger.info('✅ Test email sent')
        return True
    except Exception as e:
        logger.error(f'Email failed: {e}')
        return False


if __name__ == '__main__':
    _section('DEBUG — data_quality_check DAG (local run, no Airflow)')
    logger.info(f'DB: {os.environ.get("DATABASE_HOST")}:{os.environ.get("DATABASE_PORT")}'
                f'/{os.environ.get("DATABASE_NAME")}')

    db_ok = step_1_check_db()
    if not db_ok:
        logger.error('DB unreachable — stopping. Check Docker: docker-compose up -d')
        sys.exit(1)

    results = {
        'meta_freshness':       step_2_meta_freshness(),
        'spotify_consistency':  step_3_spotify_consistency(),
        'daily_stats':          step_4_daily_stats(),
        'summary_notification': step_5_summary(),
    }

    _section('SUMMARY')
    for task, ok in results.items():
        logger.info(f'  {"✅" if ok else "❌"}  {task}')

    failed = [k for k, v in results.items() if not v]
    if failed:
        logger.error(f'\n{len(failed)} task(s) failed: {", ".join(failed)}')
        sys.exit(1)
    else:
        logger.info('\nAll checks passed.')
