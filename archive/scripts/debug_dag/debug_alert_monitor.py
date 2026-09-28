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

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / 'airflow'))  # pour importer `dags.alert_monitor`

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

db = PostgresHandler.from_env_or_config()

# ── 1. Credential audit ───────────────────────────────────────────
# Ce bloc APPELLE la production au lieu de la réécrire. Il portait jusqu'au
# 2026-09-18 les deux moitiés du défaut que `audit-scope-restated-not-derived` a
# fermé côté DAG le 2026-08-22, et qui avaient survécu ici sans qu'un garde les
# voie : une liste de quatre plateformes écrite à la main — donc **Instagram
# n'était jamais audité** — et un test `if not creds` qui jugeait la ligne de
# stockage VIDE OU NON au lieu de juger l'identité DÉCLARÉE. Les deux se lisaient
# comme un rapport propre : celui qui exécutait ce script voyait quatre lignes
# vertes et concluait que tout était vérifié.
#
# Un script de débogage qui reformule la logique qu'il débogue ne débogue rien :
# il peut être vert quand la production est rouge, et l'inverse.
print("\n🔑 Credential audit")
from dags.alert_monitor import _mirrored_identities, _monitored_platforms  # noqa: E402
from src.utils.tenant_identity import (declared_identities,  # noqa: E402
                                       storage_platform)

platforms = _monitored_platforms()
artists = get_active_artists()
missing_creds = []
for artist_id, artist_name in artists:
    extra_by_platform = {}
    for storage in {storage_platform(p) for p in platforms}:
        try:
            extra_by_platform[storage] = load_platform_credentials(
                artist_id, storage) or {}
        except Exception as e:  # noqa: BLE001 — une ligne illisible, pas la flotte
            print(f"  ⚠️  lecture impossible {artist_name} / {storage} : "
                  f"{type(e).__name__}")
    declared = declared_identities(extra_by_platform,
                                   _mirrored_identities(artist_id))
    for platform in platforms:
        ok = platform in declared
        print(f"  {'✅' if ok else '❌ MISSING'}  {artist_name} / {platform}")
        if not ok:
            missing_creds.append({'artist_name': artist_name,
                                  'platform': platform})

print(f"\n  → {len(missing_creds)} identité(s) non déclarée(s) sur "
      f"{len(artists) * len(platforms)} combinaison(s)")

# ── 2. Freshness check ────────────────────────────────────────────
print("\n🕐 Freshness check")
results = check_freshness(db)
for r in results:
    # Before the age: an expected silence is old by definition, so reading the age
    # first prints "✅ OK (16577h)" — the same green lie as the dashboard used to.
    if r.get('expected_silence'):
        status = f"⏸️ QUIET — {r['expected_silence']}"
    elif r['age_h'] is None:
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
    ("relation does not exist", "meta_ads_api_daily"),
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
