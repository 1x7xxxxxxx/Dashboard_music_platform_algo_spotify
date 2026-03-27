"""
🐛 DEBUGGER ULTIME - INSTAGRAM PIPELINE
Ce script teste isolément chaque étape du processus Instagram :
1. Variables d'environnement (.env)
2. Connexion à la Base de Données
3. Validité du Token Meta (Appel API)
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
logger = logging.getLogger("InstaDebug")

# --- Chargement Environnement ---
load_dotenv()

# Ajout du chemin pour importer vos modules
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
    print(f"📸  {title.upper()}")
    print(f"{'='*60}")

def step_1_check_env():
    print_header("Étape 1 : Vérification .env")
    
    required = [
        "INSTAGRAM_ACCESS_TOKEN", 
        "INSTAGRAM_USER_ID", 
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
            display_val = val[:5] + "..." if "TOKEN" in var or "PASSWORD" in var else val
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
            res = db.fetch_df("SELECT count(*) FROM instagram_daily_stats")
            count = res.iloc[0,0]
            logger.info(f"   ℹ️ Table 'instagram_daily_stats' existe ({count} lignes).")
        except Exception as e:
            logger.warning(f"   ⚠️ La table semble manquer ou est vide : {e}")
            print("   💡 SQL de création suggéré :")
            print("""
            CREATE TABLE IF NOT EXISTS instagram_daily_stats (
                id SERIAL PRIMARY KEY,
                ig_user_id TEXT NOT NULL,
                username TEXT,
                followers_count INTEGER,
                follows_count INTEGER,
                media_count INTEGER,
                collected_at DATE NOT NULL
            );
            """)
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Échec connexion BDD : {e}")
        return False

def step_3_test_api():
    print_header("Étape 3 : Test API Meta (Instagram)")
    
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.getenv("INSTAGRAM_USER_ID")
    base_url = "https://graph.facebook.com/v18.0"
    
    url = f"{base_url}/{user_id}"
    params = {
        'fields': 'username,followers_count',
        'access_token': token
    }
    
    logger.info(f"📡 Appel vers : {url}")
    
    try:
        response = requests.get(url, params=params)
        
        logger.info(f"   Code HTTP : {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✅ SUCCÈS ! Token valide.")
            logger.info(f"   👤 Username : {data.get('username')}")
            logger.info(f"   📈 Abonnés : {data.get('followers_count')}")
            return data
            
        elif response.status_code == 401:
            err = response.json().get('error', {})
            logger.error("❌ ERREUR 401 (Non autorisé)")
            logger.error(f"   Message : {err.get('message')}")
            logger.error("   ➡️  Le token est expiré ou invalide.")
            
        elif response.status_code == 400:
            err = response.json().get('error', {})
            logger.error("❌ ERREUR 400 (Bad Request)")
            logger.error(f"   Message : {err.get('message')}")
            logger.error("   ➡️  Vérifiez l'ID utilisateur (INSTAGRAM_USER_ID).")
            
        else:
            logger.error(f"❌ Erreur inconnue : {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Exception Python lors de l'appel : {e}")

    return None

def step_4_dry_run_insert(api_data):
    print_header("Étape 4 : Simulation Insertion (Dry Run)")
    
    if not api_data:
        logger.warning("⏩ Pas de données API, simulation annulée.")
        return

    record = {
        'ig_user_id': api_data.get('id'),
        'username': api_data.get('username'),
        'followers_count': api_data.get('followers_count', 0),
        'follows_count': 0, # Donnée non demandée dans le test léger
        'media_count': 0,   # Idem
        'collected_at': datetime.now().strftime('%Y-%m-%d')
    }
    
    print("📝 Données prêtes pour l'insertion :")
    print(f"   {record}")
    
    print("\n🔍 Requête SQL simulée :")
    print(f"""
    DELETE FROM instagram_daily_stats WHERE collected_at = '{record['collected_at']}';
    INSERT INTO instagram_daily_stats (ig_user_id, username, followers_count, ...)
    VALUES ('{record['ig_user_id']}', '{record['username']}', {record['followers_count']}, ...);
    """)
    
    logger.info("✅ Logique de données valide.")

if __name__ == "__main__":
    if step_1_check_env():
        db_ok = step_2_check_database()
        data = step_3_test_api()
        if data:
            step_4_dry_run_insert(data)
    
    print("\n✅ Fin du diagnostic.")