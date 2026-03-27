"""
🐛 DEBUGGER ULTIME - SPOTIFY FOR ARTISTS (S4A)
Ce script simule l'exécution complète du pipeline S4A sans Airflow.
Il teste :
1. Variables d'environnement (.env)
2. Détection des fichiers CSV (Raw Directory)
3. Parsing (Extraction du nom de chanson, Dates, Streams)
4. Connexion BDD
5. Simulation d'insertion SQL (Dry Run)
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# --- Configuration Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("S4ADebug")

# --- Chargement Environnement ---
load_dotenv()

# Ajout du chemin pour importer vos modules
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Imports conditionnels
try:
    from src.database.postgres_handler import PostgresHandler
    from src.transformers.s4a_csv_parser import S4ACSVParser
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Erreur d'import critique : {e}")
    logger.error("Vérifiez que vous êtes à la racine du projet.")
    MODULES_AVAILABLE = False

# Chemins
RAW_DIR = project_root / "data" / "raw" / "spotify_for_artists"

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🎵  {title.upper()}")
    print(f"{'='*60}")

def step_1_check_env():
    print_header("Étape 1 : Vérification Environnement")
    
    # Vérif variables BDD
    vars_bdd = ["DATABASE_HOST", "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"]
    missing = [v for v in vars_bdd if not os.getenv(v)]
    
    if missing:
        logger.error(f"❌ Variables BDD manquantes : {', '.join(missing)}")
        return False
    else:
        logger.info("✅ Variables BDD détectées.")

    # Vérif Dossier
    if not RAW_DIR.exists():
        logger.warning(f"⚠️ Le dossier RAW n'existe pas : {RAW_DIR}")
        try:
            os.makedirs(RAW_DIR, exist_ok=True)
            logger.info("✅ Dossier créé.")
        except:
            logger.error("❌ Impossible de créer le dossier.")
            return False
    else:
        logger.info(f"✅ Dossier RAW présent : {RAW_DIR}")
    
    return True

def step_2_scan_files():
    print_header("Étape 2 : Scan des fichiers")
    files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.csv')]
    
    if not files:
        logger.warning("⚠️ Aucun fichier CSV trouvé.")
        logger.info("💡 Action : Déposez un fichier S4A (ex: 'Mon Titre_20251010.csv') dans 'data/raw/spotify_for_artists'")
        return []
    
    logger.info(f"✅ {len(files)} fichier(s) trouvé(s) :")
    for f in files:
        print(f"   - {f}")
    
    return files

def step_3_test_parsing(files):
    print_header("Étape 3 : Test Parsing (S4ACSVParser)")
    parser = S4ACSVParser()
    valid_data = []

    for filename in files:
        file_path = RAW_DIR / filename
        print(f"\n📄 Analyse de : {filename}")
        
        # Test extraction nom de fichier
        extracted_name = parser._extract_song_name_from_filename(filename)
        print(f"   🏷️  Nom extrait du fichier : '{extracted_name}'")

        try:
            result = parser.parse_csv_file(file_path)
            
            ftype = result.get('type')
            data = result.get('data')

            if not ftype or not data:
                logger.error(f"   ❌ Échec Parsing : Type non détecté ou Data vide.")
                logger.error(f"      - Type retourné: {ftype}")
                logger.error(f"      - Nb lignes: {len(data) if data else 0}")
                continue

            logger.info(f"   ✅ Type détecté : {ftype.upper()}")
            logger.info(f"   📊 Lignes extraites : {len(data)}")
            
            # Inspection d'un échantillon (Première et dernière ligne)
            if data:
                first = data[0]
                last = data[-1]
                print(f"      🔎 Echantillon (Ligne 1) : {first}")
                print(f"      🔎 Echantillon (Ligne {len(data)}) : {last}")
                
                # Vérification de cohérence
                if ftype == 'song_timeline' and first.get('song') != extracted_name:
                    logger.warning(f"      ⚠️ Attention : Le nom dans les données ('{first.get('song')}') diffère du nom extrait ('{extracted_name}') ?")

            valid_data.append((ftype, data))
                
        except Exception as e:
            logger.error(f"   ❌ Exception Parser : {e}")
            import traceback
            traceback.print_exc()

    return valid_data

def step_4_dry_run_db(parsed_results):
    print_header("Étape 4 : Test BDD & Simulation Insertion")
    
    if not parsed_results:
        logger.info("⏩ Pas de données à insérer. Fin.")
        return

    # Connexion
    try:
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        logger.info("✅ Connexion BDD établie.")
    except Exception as e:
        logger.error(f"❌ Échec connexion BDD : {e}")
        return

    # Simulation par Type de Fichier
    for ftype, data in parsed_results:
        print(f"\n🔹 Simulation pour Type : {ftype.upper()} ({len(data)} lignes)")
        
        if not data: continue
        sample = data[0]

        if ftype == 'song_timeline':
            print(f"   🎯 Table Cible : s4a_song_timeline")
            print(f"   🔑 Clé d'unicité (Conflict) : ['song', 'date']")
            print(f"   📝 Colonnes à Update : ['streams', 'collected_at']")
            
            print("   📝 Requête SQL simulée (Upsert) :")
            print(f"""
            INSERT INTO s4a_song_timeline (song, date, streams)
            VALUES ('{sample['song']}', '{sample['date']}', {sample['streams']})
            ON CONFLICT (song, date) DO UPDATE 
            SET streams = EXCLUDED.streams, collected_at = NOW();
            """)
            
        elif ftype == 'audience':
            print(f"   🎯 Table Cible : s4a_audience")
            print(f"   🔑 Clé d'unicité (Conflict) : ['date']")
            print("   📝 Requête SQL simulée :")
            print(f"""
            INSERT INTO s4a_audience (date, listeners, streams, followers)
            VALUES ('{sample.get('date')}', ...)
            ON CONFLICT (date) DO UPDATE ...
            """)
            
        elif ftype == 'songs_global':
             print(f"   🎯 Table Cible : s4a_songs_global")
             print(f"   🔑 Clé d'unicité (Conflict) : ['song']")
             print("   📝 Requête SQL simulée :")
             print(f"""
             INSERT INTO s4a_songs_global (song, listeners, ...)
             VALUES ('{sample.get('song')}', ...)
             ON CONFLICT (song) DO UPDATE ...
             """)

    db.close()

if __name__ == "__main__":
    if not MODULES_AVAILABLE:
        sys.exit(1)
        
    if step_1_check_env():
        files = step_2_scan_files()
        if files:
            results = step_3_test_parsing(files)
            step_4_dry_run_db(results)
    
    print("\n✅ Debugging terminé.")