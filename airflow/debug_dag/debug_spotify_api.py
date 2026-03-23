"""
🐛 DEBUGGER ULTIME - SPOTIFY API PIPELINE
Ce script teste isolément chaque étape du processus Spotify :
1. Variables d'environnement (.env)
2. Authentification Spotify (Client ID/Secret)
3. Collecte API (Artiste + Top Tracks)
4. Connexion BDD
5. Simulation d'insertion SQL (Dry Run)
"""

import os
import sys
import logging
from datetime import datetime, date
from dotenv import load_dotenv
from pathlib import Path

# --- Configuration Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("SpotifyDebug")

# --- Chargement Environnement ---
load_dotenv()

# Ajout du chemin pour importer vos modules
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Import conditionnel
try:
    from src.collectors.spotify_api import SpotifyCollector
    from src.database.postgres_handler import PostgresHandler
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Erreur d'import critique : {e}")
    logger.error("Vérifiez que vous êtes à la racine du projet.")
    MODULES_AVAILABLE = False

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🎵  {title.upper()}")
    print(f"{'='*60}")

def step_1_check_env():
    print_header("Étape 1 : Vérification .env")
    
    required = [
        "SPOTIFY_CLIENT_ID", 
        "SPOTIFY_CLIENT_SECRET", 
        "SPOTIFY_ARTIST_IDS",
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
            display_val = val[:5] + "..." if "SECRET" in var or "PASSWORD" in var else val
            if var == "SPOTIFY_ARTIST_IDS":
                ids = val.split(',')
                display_val = f"{len(ids)} ID(s) configuré(s) (ex: {ids[0]})"
            logger.info(f"✅ {var} = {display_val}")

    if missing:
        logger.error(f"❌ Variables manquantes : {', '.join(missing)}")
        return False
    return True

def step_2_test_api_auth():
    print_header("Étape 2 : Test Authentification API")
    
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    
    try:
        collector = SpotifyCollector(client_id, client_secret)
        # Test simple : chercher "Daft Punk" pour valider le token
        res = collector.search_artist("Daft Punk")
        if res:
            logger.info("✅ Authentification réussie (Recherche test OK).")
            return collector
        else:
            logger.warning("⚠️ Authentification semble OK mais recherche vide.")
            return collector
    except Exception as e:
        logger.error(f"❌ Échec Authentification : {e}")
        return None

def step_3_collect_data(collector):
    print_header("Étape 3 : Test Collecte Données")
    
    artist_ids = os.getenv('SPOTIFY_ARTIST_IDS', '').split(',')
    # On teste seulement sur le premier artiste pour aller vite
    test_id = artist_ids[0].strip()
    
    if not test_id:
        logger.warning("⚠️ Aucun ID artiste valide trouvé.")
        return None

    logger.info(f"🧪 Test sur l'artiste ID : {test_id}")
    
    # 1. Info Artiste
    logger.info("   [A] Récupération Infos Artiste...")
    artist_info = collector.get_artist_info(test_id)
    
    if artist_info:
        logger.info(f"       ✅ Nom : {artist_info['name']}")
        logger.info(f"       ✅ Followers : {artist_info['followers']}")
        logger.info(f"       ✅ Popularité : {artist_info['popularity']}")
    else:
        logger.error("       ❌ Échec récupération artiste.")
        return None

    # 2. Top Tracks
    logger.info("   [B] Récupération Top Tracks...")
    tracks = collector.get_artist_top_tracks(test_id)
    
    if tracks:
        logger.info(f"       ✅ {len(tracks)} tracks trouvées.")
        logger.info(f"       🎵 Top 1 : {tracks[0]['track_name']} (Pop: {tracks[0]['popularity']})")
    else:
        logger.warning("       ⚠️ Aucune track trouvée.")

    return {'artist': artist_info, 'tracks': tracks}

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
        tables = ['artists', 'tracks', 'artist_history', 'track_popularity_history']
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

    artist = data['artist']
    tracks = data['tracks']

    # Simulation Artist Upsert
    print("\n🔹 [Table: artists] (Upsert)")
    print(f"   Clé : {artist['artist_id']}")
    print(f"   Valeurs : Followers={artist['followers']}, Pop={artist['popularity']}")
    print("   SQL : INSERT ... ON CONFLICT (artist_id) DO UPDATE ...")

    # Simulation Artist History
    print("\n🔹 [Table: artist_history] (Insert Snapshot)")
    print(f"   SQL : INSERT INTO artist_history (artist_id, followers, popularity, collected_at)")
    print(f"         VALUES ('{artist['artist_id']}', {artist['followers']}, {artist['popularity']}, NOW())")

    # Simulation Tracks
    if tracks:
        t = tracks[0]
        print(f"\n🔹 [Table: tracks] (Upsert x {len(tracks)})")
        print(f"   Exemple : '{t['track_name']}' (ID: {t['track_id']})")
        print("   SQL : INSERT ... ON CONFLICT (track_id) DO UPDATE ...")

        # Simulation Track Popularity History
        print("\n🔹 [Table: track_popularity_history] (Insert Snapshot)")
        print(f"   Clé Unique : Track ID + Date du jour ({date.today()})")
        print(f"   SQL : INSERT INTO track_popularity_history (track_id, popularity, date) ...")
        print(f"         ON CONFLICT (track_id, date) DO UPDATE ...")

    logger.info("✅ Logique d'insertion valide.")

if __name__ == "__main__":
    if not MODULES_AVAILABLE:
        sys.exit(1)

    if step_1_check_env():
        collector = step_2_test_api_auth()
        if collector:
            data = step_3_collect_data(collector)
            if step_4_check_database() and data:
                step_5_dry_run_insert(data)
    
    print("\n✅ Debugging terminé.")