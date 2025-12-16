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

# Ajout du chemin pour importer vos modules
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

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

if __name__ == "__main__":
    if step_1_check_env():
        db_ok = step_2_check_database()
        data = step_3_test_api()
        if data:
            step_4_dry_run_insert(data)
    
    print("\n✅ Fin du diagnostic.")