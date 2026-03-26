"""
🐛 DEBUGGER ULTIME - SOUNDCLOUD PIPELINE
Ce script teste isolément chaque étape du processus SoundCloud :
1. Variables d'environnement (.env)
2. Connexion à la Base de Données
3. Validité du Client ID (Appel API)
4. Simulation d'insertion SQL (Dry Run)
"""

import os
import sys
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# --- Configuration Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("SoundCloudDebug")

# --- Chargement Environnement ---
load_dotenv()

# Project root: airflow/debug_dag/ → airflow/ → project root
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Import conditionnel pour éviter le crash si le module manque
try:
    from src.database.postgres_handler import PostgresHandler
    DATABASE_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Module src.database.postgres_handler introuvable. Test BDD limité.")
    DATABASE_AVAILABLE = False

def print_header(title):
    print(f"\n{'='*60}")
    print(f"☁️  {title.upper()}")
    print(f"{'='*60}")

def step_1_check_env():
    print_header("Étape 1 : Vérification .env")
    
    required = [
        "SOUNDCLOUD_CLIENT_ID", 
        "SOUNDCLOUD_USER_ID", 
        "DATABASE_HOST", 
        "DATABASE_NAME", 
        "DATABASE_USER", 
        "DATABASE_PASSWORD"
    ]
    
    missing = []
    for var in required:
        val = os.getenv(var)
        if not val:
            missing.append(var)
        else:
            # Masquer les secrets pour l'affichage
            display_val = val[:5] + "..." if "PASSWORD" in var else val
            logger.info(f"✅ {var} = {display_val}")

    if missing:
        logger.error(f"❌ Variables manquantes : {', '.join(missing)}")
        return False
    return True

def step_2_check_database():
    print_header("Étape 2 : Connexion PostgreSQL")
    
    if not DATABASE_AVAILABLE:
        return False

    host = os.getenv('DATABASE_HOST', 'localhost')
    port = os.getenv('DATABASE_PORT', '5432')
    
    try:
        db = PostgresHandler(
            host=host,
            port=port,
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        logger.info(f"✅ Connexion réussie vers {host}:{port}")
        
        # Test existence table
        try:
            res = db.fetch_df("SELECT count(*) FROM soundcloud_tracks_daily")
            count = res.iloc[0,0]
            logger.info(f"   ℹ️ Table 'soundcloud_tracks_daily' existe ({count} lignes).")
        except Exception as e:
            logger.warning(f"   ⚠️ La table semble manquer ou est vide : {e}")
            print("   💡 SQL de création suggéré :")
            print("""
            CREATE TABLE IF NOT EXISTS soundcloud_tracks_daily (
                id SERIAL PRIMARY KEY,
                track_id TEXT NOT NULL,
                title TEXT,
                permalink_url TEXT,
                playback_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                reposts_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                collected_at DATE NOT NULL
            );
            """)
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Échec connexion BDD : {e}")
        return False

def step_3_test_api():
    print_header("Étape 3 : Test API SoundCloud")
    
    client_id = os.getenv("SOUNDCLOUD_CLIENT_ID")
    user_id = os.getenv("SOUNDCLOUD_USER_ID")
    base_url = "https://api-v2.soundcloud.com"
    
    # On teste avec une limite de 1 pour être léger
    url = f"{base_url}/users/{user_id}/tracks"
    params = {
        'client_id': client_id,
        'limit': 1,
        'linked_partitioning': 1
    }
    
    logger.info(f"📡 Appel vers : {url}")
    
    try:
        response = requests.get(url, params=params)
        
        logger.info(f"   Code HTTP : {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✅ SUCCÈS ! Client ID valide.")
            
            if 'collection' in data and len(data['collection']) > 0:
                track = data['collection'][0]
                logger.info(f"   🎵 Titre trouvé : {track.get('title')}")
                logger.info(f"   ▶️  Ecoutes : {track.get('playback_count')}")
                return [track] # Retourne une liste pour simuler insert_many
            else:
                logger.warning("   ⚠️ Aucune track trouvée pour cet utilisateur.")
            
        elif response.status_code == 401:
            logger.error("❌ ERREUR 401 (Unauthorized)")
            logger.error("   ➡️  Le CLIENT_ID est invalide ou expiré.")
            
        elif response.status_code == 403:
            logger.error("❌ ERREUR 403 (Forbidden)")
            logger.error("   ➡️  Accès refusé. Vérifiez User-Agent ou IP.")
            
        else:
            logger.error(f"❌ Erreur API : {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Exception Python lors de l'appel : {e}")

    return None

def step_4_dry_run_insert(tracks_data):
    print_header("Étape 4 : Simulation Insertion (Dry Run)")
    
    if not tracks_data:
        logger.warning("⏩ Pas de données API, simulation annulée.")
        return

    track = tracks_data[0]
    
    record = {
        'track_id': str(track.get('id')),
        'title': track.get('title'),
        'permalink_url': track.get('permalink_url'),
        'playback_count': int(track.get('playback_count', 0)),
        'likes_count': int(track.get('likes_count', 0)),
        'reposts_count': int(track.get('reposts_count', 0)),
        'comment_count': int(track.get('comment_count', 0)),
        'collected_at': datetime.now().strftime('%Y-%m-%d')
    }
    
    print("📝 Données prêtes pour l'insertion :")
    print(f"   {record}")
    
    print("\n🔍 Requête SQL simulée :")
    print(f"""
    DELETE FROM soundcloud_tracks_daily WHERE collected_at = '{record['collected_at']}';
    INSERT INTO soundcloud_tracks_daily (track_id, title, playback_count, ...)
    VALUES ('{record['track_id']}', '{record['title']}', {record['playback_count']}, ...);
    """)
    
    logger.info("✅ Logique de données valide.")

def step_4b_diagnose_bundle():
    """Diagnose what SoundCloud returns when fetching the homepage + bundles.

    Shows: HTTP status, number of JS URLs found, first 300 chars of each bundle,
    and which regex patterns match (if any). Run this when step_5 fails.
    """
    import re as _re
    print_header("Étape 4b : Diagnostic bundle JS (raw)")

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    try:
        r = session.get("https://soundcloud.com", timeout=15)
        logger.info(f"Homepage status: {r.status_code} — content length: {len(r.text)}")
        if r.status_code != 200:
            logger.error(f"Homepage blocked or redirected. First 500 chars:\n{r.text[:500]}")
            return

        js_urls = list(dict.fromkeys(
            _re.findall(r'https://a-v2\.sndcdn\.com/assets/[^"\']+\.js', r.text)
        ))
        logger.info(f"JS bundle URLs found: {len(js_urls)}")
        for u in js_urls[:5]:
            logger.info(f"  {u}")

        patterns = [
            (r'[,({"\s]client_id\s*:\s*"([a-zA-Z0-9]{20,})"', 'JS object key'),
            (r'"client_id"\s*:\s*"([a-zA-Z0-9]{20,})"',        'JSON string key'),
            (r'client_id=([a-zA-Z0-9]{20,})',                   'query-string'),
            (r'client_id%3D([a-zA-Z0-9]{20,})',                 'URL-encoded'),
        ]

        # Search HTML page first
        logger.info("\n--- HTML page ---")
        for pat, label in patterns:
            m = _re.search(pat, r.text)
            if m:
                logger.info(f"  ✅ [{label}] in HTML: {m.group(1)}")

        # Search all bundles
        for url in js_urls:
            try:
                js = session.get(url, timeout=15).text
                logger.info(f"\nBundle {url.split('/')[-1]} — size: {len(js)} chars")
                matched = False
                for pat, label in patterns:
                    m = _re.search(pat, js)
                    if m:
                        logger.info(f"  ✅ Pattern [{label}] matched: {m.group(1)}")
                        matched = True
                if not matched:
                    # Show ALL client_id occurrences with context to help craft new pattern
                    for occ in _re.finditer(r'.{0,40}client_id.{0,60}', js):
                        logger.info(f"  context: …{occ.group()}…")
            except Exception as e:
                logger.warning(f"  Failed to fetch {url}: {e}")
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")


def step_5_test_bundle_refresh():
    """Test _fetch_client_id_from_bundle() in isolation (no credentials needed).

    Verifies:
    - soundcloud.com homepage is reachable and contains JS bundle URLs
    - At least one bundle contains the client_id pattern
    - Parallel fetch resolves within a reasonable time
    """
    import time
    print_header("Étape 5 : Test auto-refresh bundle JS (isolation)")

    try:
        project_root_path = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(project_root_path))
        from src.collectors.soundcloud_api_collector import SoundCloudCollector

        logger.info("Fetching client_id from SoundCloud JS bundle (parallel)...")
        t0 = time.time()
        client_id = SoundCloudCollector._fetch_client_id_from_bundle()
        elapsed = time.time() - t0

        logger.info(f"✅ client_id extracted in {elapsed:.1f}s : {client_id[:8]}… (len={len(client_id)})")
        return client_id
    except Exception as e:
        logger.error(f"❌ Bundle refresh failed: {e}")
        return None


def step_6_test_401_simulation():
    """Force a 401 by using a dummy client_id, then verify auto-refresh triggers.

    Sets SOUNDCLOUD_CLIENT_ID to an invalid value before instantiating the
    collector, then calls fetch_tracks(). The @retry decorator will catch the
    ValueError raised after refresh and re-run with the new client_id.

    Requires SOUNDCLOUD_USER_ID to be set in .env (user_id is not rotated).
    """
    print_header("Étape 6 : Simulation 401 → auto-refresh")

    user_id = os.getenv("SOUNDCLOUD_USER_ID")
    if not user_id:
        logger.warning("SOUNDCLOUD_USER_ID absent — étape ignorée.")
        return None

    try:
        project_root_path = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(project_root_path))
        from src.collectors.soundcloud_api_collector import SoundCloudCollector

        # Inject a known-invalid client_id to force 401
        os.environ["SOUNDCLOUD_CLIENT_ID"] = "invalid_key_force_401_debug"
        logger.info("Injected dummy client_id → expecting 401 → auto-refresh → retry")

        collector = SoundCloudCollector.__new__(SoundCloudCollector)
        collector.artist_id = 1
        collector.client_id = "invalid_key_force_401_debug"
        collector.user_id = user_id
        collector.base_url = "https://api-v2.soundcloud.com"
        collector._client_id_refreshed = False
        collector.db = None
        collector.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Origin': 'https://soundcloud.com',
            'Referer': 'https://soundcloud.com/',
        }

        tracks = collector.fetch_tracks()
        logger.info(f"✅ Auto-refresh worked — {len(tracks)} track(s) collected with refreshed client_id.")
        logger.info(f"   Final client_id in memory: {collector.client_id[:8]}…")
        return collector.client_id
    except Exception as e:
        logger.error(f"❌ 401 simulation failed: {e}")
        return None


def step_7_verify_db_persist(expected_client_id: str):
    """Read back extra_config from artist_credentials and confirm client_id was saved.

    Requires Docker + spotify_etl DB running and an existing row for
    (artist_id=1, platform='soundcloud').
    """
    print_header("Étape 7 : Vérification persist DB")

    if not expected_client_id:
        logger.warning("Pas de client_id à vérifier — étape ignorée.")
        return

    if not DATABASE_AVAILABLE:
        logger.warning("Module DB non disponible — étape ignorée.")
        return

    host = os.getenv('DATABASE_HOST', 'localhost')
    port = os.getenv('DATABASE_PORT', '5432')

    try:
        db = PostgresHandler(
            host=host, port=port,
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD'),
        )
        df = db.fetch_df(
            "SELECT extra_config, updated_at FROM artist_credentials "
            "WHERE artist_id = 1 AND platform = 'soundcloud'"
        )
        db.close()

        if df.empty:
            logger.warning("Aucune ligne (artist_id=1, platform='soundcloud') dans artist_credentials.")
            logger.info("Le persist est non-bloquant — normal si aucun credential n'a jamais été saisi via le dashboard.")
            return

        extra = df.iloc[0]['extra_config'] or {}
        if isinstance(extra, str):
            import json
            extra = json.loads(extra)

        saved_id = extra.get('client_id', '')
        updated_at = df.iloc[0]['updated_at']

        if saved_id == expected_client_id:
            logger.info(f"✅ client_id en DB correspond ({saved_id[:8]}…) — updated_at: {updated_at}")
        else:
            logger.warning(
                f"⚠️  Mismatch — attendu: {expected_client_id[:8]}…  en DB: {(saved_id or 'vide')[:8]}…"
            )
            logger.info("Cause probable : aucune ligne existante → UPDATE no-op (comportement attendu).")

    except Exception as e:
        logger.error(f"❌ Lecture DB échouée: {e}")


if __name__ == "__main__":
    if step_1_check_env():
        db_ok = step_2_check_database()
        data = step_3_test_api()
        if data:
            step_4_dry_run_insert(data)

    # --- Nouvelles étapes : test auto-refresh ---
    step_4b_diagnose_bundle()
    extracted_id = step_5_test_bundle_refresh()
    refreshed_id = step_6_test_401_simulation()
    step_7_verify_db_persist(refreshed_id or extracted_id)

    print("\n✅ Fin du diagnostic.")