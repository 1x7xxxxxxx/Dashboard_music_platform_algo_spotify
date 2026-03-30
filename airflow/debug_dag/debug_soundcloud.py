"""Debug script for soundcloud_daily DAG — OAuth 2.0 Client Credentials flow.

Run locally (outside Airflow) to validate credentials and API connectivity:
    python airflow/debug_dag/debug_soundcloud.py

Requires .env with:
    SOUNDCLOUD_CLIENT_ID, SOUNDCLOUD_CLIENT_SECRET, SOUNDCLOUD_USER_ID
    DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD
"""
import os
import sys
import time
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

_TOKEN_ENDPOINT = "https://api.soundcloud.com/oauth2/token"
_API_BASE = "https://api.soundcloud.com"
SEP = "=" * 60


def section(title: str) -> None:
    print(f"\n{SEP}\n☁️  {title}\n{SEP}")


# ── Étape 1 : Variables d'environnement ──────────────────────────────────────
section("ÉTAPE 1 : VÉRIFICATION .ENV")

required = {
    'SOUNDCLOUD_CLIENT_ID':     os.getenv('SOUNDCLOUD_CLIENT_ID'),
    'SOUNDCLOUD_CLIENT_SECRET': os.getenv('SOUNDCLOUD_CLIENT_SECRET'),
    'SOUNDCLOUD_USER_ID':       os.getenv('SOUNDCLOUD_USER_ID'),
    'DATABASE_HOST':            os.getenv('DATABASE_HOST'),
    'DATABASE_NAME':            os.getenv('DATABASE_NAME'),
    'DATABASE_USER':            os.getenv('DATABASE_USER'),
    'DATABASE_PASSWORD':        os.getenv('DATABASE_PASSWORD'),
}

all_ok = True
for key, val in required.items():
    if val:
        display = val[:8] + '...' if 'SECRET' in key or 'PASSWORD' in key else val
        logger.info(f"✅ {key} = {display}")
    else:
        logger.error(f"❌ {key} manquant dans .env")
        all_ok = False

if not all_ok:
    logger.error("Variables manquantes — arrêt du diagnostic.")
    sys.exit(1)

CLIENT_ID     = required['SOUNDCLOUD_CLIENT_ID']
CLIENT_SECRET = required['SOUNDCLOUD_CLIENT_SECRET']
USER_ID       = required['SOUNDCLOUD_USER_ID']


# ── Étape 2 : Connexion PostgreSQL ──────────────────────────────────────────
section("ÉTAPE 2 : CONNEXION POSTGRESQL")

try:
    from src.database.postgres_handler import PostgresHandler
    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST'),
        port=os.getenv('DATABASE_PORT', '5433'),
        database=os.getenv('DATABASE_NAME'),
        user=os.getenv('DATABASE_USER'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    logger.info(f"✅ Connecté à PostgreSQL: {os.getenv('DATABASE_NAME')}")
    row = db.fetch_query("SELECT count(*) FROM soundcloud_tracks_daily")
    logger.info(f"   ℹ️ Table 'soundcloud_tracks_daily' existe ({row[0][0]} lignes).")
    db.close()
    logger.info("🔒 Connexion PostgreSQL fermée")
except Exception as e:
    logger.error(f"❌ Connexion PostgreSQL échouée : {e}")


# ── Étape 3 : OAuth token endpoint ─────────────────────────────────────────
section("ÉTAPE 3 : TEST OAUTH TOKEN ENDPOINT")

access_token = None
try:
    t0 = time.time()
    r = requests.post(
        _TOKEN_ENDPOINT,
        data={
            'grant_type':    'client_credentials',
            'client_id':     CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        },
        timeout=15,
    )
    elapsed = time.time() - t0
    logger.info(f"   Code HTTP : {r.status_code} (en {elapsed:.2f}s)")

    if r.status_code == 200:
        data = r.json()
        access_token = data.get('access_token')
        expires_in   = data.get('expires_in', '?')
        logger.info(f"✅ Access token obtenu : {access_token[:8]}… (expire dans {expires_in}s)")
    elif r.status_code == 401:
        logger.error("❌ 401 — client_id ou client_secret invalide.")
        logger.error(f"   Réponse : {r.text[:300]}")
    else:
        logger.error(f"❌ HTTP {r.status_code} : {r.text[:300]}")
except Exception as e:
    logger.error(f"❌ Erreur réseau : {e}")

if not access_token:
    logger.error("Token absent — impossible de tester l'API. Vérifier client_id / client_secret.")
    sys.exit(1)


# ── Étape 4 : Test API officielle ──────────────────────────────────────────
section("ÉTAPE 4 : TEST API OFFICIELLE (GET /users/{user_id}/tracks)")

try:
    r = requests.get(
        f"{_API_BASE}/users/{USER_ID}/tracks",
        headers={'Authorization': f'OAuth {access_token}'},
        params={'limit': 3, 'linked_partitioning': 1},
        timeout=15,
    )
    logger.info(f"   Code HTTP : {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        tracks = data.get('collection', [])
        logger.info(f"✅ {len(tracks)} track(s) récupéré(s) (page 1, limit=3)")
        for t in tracks:
            logger.info(
                f"   🎵 [{t.get('id')}] {t.get('title', '?')} — "
                f"plays={t.get('playback_count', 0)} likes={t.get('likes_count', 0)}"
            )
    elif r.status_code == 401:
        logger.error("❌ 401 — token invalide ou révoqué.")
    elif r.status_code == 404:
        logger.error(f"❌ 404 — User ID '{USER_ID}' introuvable. Vérifier que c'est bien l'ID numérique.")
    else:
        logger.error(f"❌ HTTP {r.status_code} : {r.text[:300]}")
except Exception as e:
    logger.error(f"❌ Erreur réseau : {e}")


# ── Étape 5 : Test expiry guard ────────────────────────────────────────────
section("ÉTAPE 5 : TEST EXPIRY GUARD (SIMULATION TOKEN EXPIRÉ)")

try:
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    collector = SoundCloudCollector(
        artist_id=1,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        user_id=USER_ID,
    )
    # Force expiry to verify auto-renew
    collector._token_expires_at = 0.0
    collector._ensure_token()
    logger.info(f"✅ Token renouvelé automatiquement : {collector._access_token[:8]}…")
    collector.db.close()
except Exception as e:
    logger.error(f"❌ Expiry guard failed : {e}")


# ── Fin ────────────────────────────────────────────────────────────────────
print(f"\n✅ Fin du diagnostic.")
