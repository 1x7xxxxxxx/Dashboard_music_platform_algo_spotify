"""
🐛 DEBUGGER ULTIME - YOUTUBE API PIPELINE
Ce script teste isolément chaque étape du processus YouTube :
1. Variables d'environnement (.env)
2. Authentification Google API (Clé API)
3. Collecte API (Stats Chaîne + Vidéos)
4. Connexion BDD
5. Simulation d'insertion SQL (Dry Run)
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# --- Configuration Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("YouTubeDebug")

# --- Chargement Environnement ---
load_dotenv()

# Ajout du chemin pour importer vos modules
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Import conditionnel pour éviter le crash si le module manque
try:
    from src.collectors.youtube_collector import YouTubeCollector
    from src.database.postgres_handler import PostgresHandler
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Erreur d'import critique : {e}")
    logger.error("Vérifiez que vous êtes à la racine du projet.")
    MODULES_AVAILABLE = False

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🎬  {title.upper()}")
    print(f"{'='*60}")

def step_1_check_env():
    print_header("Étape 1 : Vérification .env")
    
    required = [
        "YOUTUBE_API_KEY", 
        "YOUTUBE_CHANNEL_ID",
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
            # Masquer les secrets
            display_val = val[:5] + "..." if "KEY" in var or "PASSWORD" in var else val
            logger.info(f"✅ {var} = {display_val}")

    if missing:
        logger.error(f"❌ Variables manquantes : {', '.join(missing)}")
        return False
    return True

def step_2_test_api_auth():
    print_header("Étape 2 : Test Authentification API")
    
    api_key = os.getenv('YOUTUBE_API_KEY')
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    
    try:
        collector = YouTubeCollector(api_key)
        # Test simple : récupérer les stats de la chaîne configurée
        stats = collector.get_channel_stats(channel_id)
        
        if stats:
            logger.info(f"✅ Authentification réussie.")
            logger.info(f"   📺 Nom de la chaîne : {stats.get('channel_name')}")
            logger.info(f"   👥 Abonnés : {stats.get('subscriber_count')}")
            return collector
        else:
            logger.error("❌ Échec : Clé API valide mais chaîne introuvable (ID incorrect ?).")
            return None
            
    except Exception as e:
        logger.error(f"❌ Échec Authentification : {e}")
        return None

def step_3_collect_sample_data(collector):
    print_header("Étape 3 : Test Collecte Données (Échantillon)")
    
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    
    # 1. Stats Chaîne (Déjà testé en étape 2, mais on garde pour la structure)
    channel_stats = collector.get_channel_stats(channel_id)
    
    # 2. Vidéos (Juste les 5 dernières pour le test)
    logger.info("   [B] Récupération de 5 vidéos récentes...")
    videos = collector.get_channel_videos(channel_id, max_results=5)
    
    if videos:
        logger.info(f"       ✅ {len(videos)} vidéos trouvées.")
        first_video = videos[0]
        logger.info(f"       📹 Récente : '{first_video.get('title')}' (ID: {first_video.get('video_id')})")
        
        # 3. Stats Vidéos
        logger.info("   [C] Récupération Stats Vidéos...")
        video_ids = [v['video_id'] for v in videos]
        video_stats = collector.get_video_stats(video_ids)
        
        if video_stats:
            v_stat = video_stats[0]
            logger.info(f"       📊 Vues : {v_stat.get('view_count')} | Likes : {v_stat.get('like_count')}")
        else:
            logger.warning("       ⚠️ Impossible de récupérer les stats vidéos.")
    else:
        logger.warning("       ⚠️ Aucune vidéo trouvée sur cette chaîne.")
        video_stats = []

    return {
        'channel_stats': channel_stats,
        'videos': videos,
        'video_stats': video_stats
    }

def step_4_check_database():
    print_header("Étape 4 : Connexion BDD")
    
    try:
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        logger.info("✅ Connexion réussie.")
        
        # Vérif Tables
        tables = ['youtube_channels', 'youtube_channel_history', 'youtube_videos', 'youtube_video_stats']
        for t in tables:
            try:
                db.fetch_df(f"SELECT 1 FROM {t} LIMIT 1")
                logger.info(f"   ✅ Table '{t}' détectée.")
            except Exception:
                logger.warning(f"   ⚠️ Table '{t}' manquante ou erreur d'accès.")
        
        db.close()
        return True
    except Exception as e:
        logger.error(f"❌ Échec BDD : {e}")
        return False

def step_5_dry_run_insert(data):
    print_header("Étape 5 : Simulation Insertion (Dry Run)")
    
    if not data:
        logger.info("⏩ Pas de données à insérer.")
        return

    c_stats = data['channel_stats']
    videos = data['videos']
    v_stats = data['video_stats']

    # 1. Chaîne
    if c_stats:
        print("\n🔹 [Table: youtube_channels] (Upsert)")
        print(f"   Clé : {c_stats['channel_id']}")
        print(f"   Valeurs : Vues={c_stats['view_count']}, Subs={c_stats['subscriber_count']}")
        
        print("\n🔹 [Table: youtube_channel_history] (Insert Snapshot)")
        print(f"   SQL : INSERT INTO youtube_channel_history (channel_id, subscriber_count, view_count, collected_at)...")

    # 2. Vidéos
    if videos:
        v = videos[0]
        print(f"\n🔹 [Table: youtube_videos] (Upsert x {len(videos)})")
        print(f"   Exemple : '{v['title']}'")
        print(f"   SQL : INSERT ... ON CONFLICT (video_id) DO UPDATE ...")

    # 3. Stats Vidéos
    if v_stats:
        s = v_stats[0]
        print(f"\n🔹 [Table: youtube_video_stats] (Insert History)")
        print(f"   Exemple ID : {s['video_id']} (Vues: {s['view_count']})")
        print(f"   SQL : INSERT INTO youtube_video_stats (video_id, view_count, like_count, ...) VALUES ...")
        
        print("\n🔹 [Table: youtube_videos] (Update Metadata)")
        print(f"   SQL : UPDATE youtube_videos SET duration = '{s.get('duration')}' WHERE video_id = '{s['video_id']}'")

    logger.info("✅ Logique d'insertion valide.")

if __name__ == "__main__":
    if not MODULES_AVAILABLE:
        sys.exit(1)

    if step_1_check_env():
        collector = step_2_test_api_auth()
        if collector:
            data = step_3_collect_sample_data(collector)
            if step_4_check_database() and data:
                step_5_dry_run_insert(data)
    
    print("\n✅ Debugging terminé.")