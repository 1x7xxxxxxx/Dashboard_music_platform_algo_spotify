"""Debug script for alert_monitor DAG — runs locally without Airflow.

Usage:
    python airflow/debug_dag/debug_alert_monitor.py

Requires:
    - Docker postgres running (port 5433 locally)
    - config/config.yaml with DB credentials
    - SMTP env vars set (or will warn and skip email)
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Load config to set DB env vars
from src.utils.config_loader import config_loader
config = config_loader.load()
db_conf = config.get('database', {})
os.environ.setdefault('DATABASE_HOST', db_conf.get('host', 'localhost'))
os.environ.setdefault('DATABASE_PORT', str(db_conf.get('port', 5433)))
os.environ.setdefault('DATABASE_NAME', db_conf.get('database', 'spotify_etl'))
os.environ.setdefault('DATABASE_USER', db_conf.get('user', 'postgres'))
os.environ.setdefault('DATABASE_PASSWORD', db_conf.get('password', ''))

from src.database.postgres_handler import PostgresHandler
from src.utils.freshness_monitor import check_freshness
from src.utils.credential_loader import get_active_artists, load_platform_credentials
from src.utils.alert_root_cause import detect_root_cause

print("=" * 70)
print("DEBUG alert_monitor")
print("=" * 70)

db = PostgresHandler(
    host=os.environ['DATABASE_HOST'],
    port=int(os.environ['DATABASE_PORT']),
    database=os.environ['DATABASE_NAME'],
    user=os.environ['DATABASE_USER'],
    password=os.environ['DATABASE_PASSWORD'],
)

# ── 1. Credential audit ───────────────────────────────────────────
print("\n🔑 Credential audit")
MONITORED_PLATFORMS = ['spotify', 'youtube', 'soundcloud', 'meta']
artists = get_active_artists()
missing_creds = []
for artist_id, artist_name in artists:
    for platform in MONITORED_PLATFORMS:
        creds = load_platform_credentials(artist_id, platform)
        status = '✅' if creds else '❌ MISSING'
        print(f"  {status}  {artist_name} / {platform}")
        if not creds:
            missing_creds.append({'artist_name': artist_name, 'platform': platform})

print(f"\n  → {len(missing_creds)} credential(s) manquant(s)")

# ── 2. Freshness check ────────────────────────────────────────────
print("\n🕐 Freshness check")
results = check_freshness(db)
for r in results:
    if r['age_h'] is None:
        status = '⚫ NEVER'
    elif r['stale']:
        status = f"🔴 STALE ({r['age_h']:.0f}h > {r['stale_h']}h)"
    else:
        status = f"✅ OK ({r['age_h']:.0f}h)"
    print(f"  {r['source']:20s} {status}")

# ── 3. Root cause test ────────────────────────────────────────────
print("\n🔍 Root cause detection test")
test_cases = [
    ("401 Unauthorized", "soundcloud_daily"),
    ("connection refused", "youtube_daily"),
    ("relation does not exist", "meta_insights_dag"),
    ("timeout", "instagram_daily"),
    ("", "spotify_api_daily"),
]
for exc, dag in test_cases:
    cause, action = detect_root_cause(exc, dag)
    print(f"  [{dag}] '{exc[:30]}...' → {cause}")
    print(f"    Action: {action}")

db.close()
print("\n" + "=" * 70)
print("Debug terminé.")
