"""
🐛 DEBUGGER ULTIME - APPLE MUSIC PIPELINE
Ce script simule l'exécution complète du DAG Apple Music sans Airflow.
Il teste :
1. La détection des fichiers
2. Le parsing (Encodage, Colonnes, Types)
3. La connexion BDD
4. La logique d'insertion (Dry Run)
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# Configuration du Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Debugger")

# Charger les variables d'environnement
load_dotenv()

# Ajouter le chemin racine pour les imports
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Import des modules du projet
try:
    from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
    from src.database.postgres_handler import PostgresHandler
except ImportError as e:
    logger.error(f"❌ Erreur d'import : {e}")
    logger.error("Vérifiez que vous lancez le script depuis la racine du projet.")
    sys.exit(1)

# Configuration
RAW_DIR = Path('/opt/airflow/data/raw/apple_music')  # Mettez votre chemin local si hors docker
PROCESSED_DIR = Path('/opt/airflow/data/processed/apple_music')

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🛠️  {title.upper()}")
    print(f"{'='*60}")

def step_1_check_environment():
    print_header("Étape 1 : Vérification de l'environnement")
    
    # 1. Vérification Dossiers
    if not RAW_DIR.exists():
        logger.warning(f"⚠️ Dossier RAW introuvable : {RAW_DIR}")
        try:
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Dossier créé : {RAW_DIR}")
        except Exception as e:
            logger.error(f"❌ Impossible de créer le dossier : {e}")
            return False
    else:
        logger.info(f"✅ Dossier RAW existant : {RAW_DIR}")

    # 2. Vérification Variables BDD
    required_vars = ['DATABASE_HOST', 'DATABASE_NAME', 'DATABASE_USER', 'DATABASE_PASSWORD']
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"❌ Variables d'environnement manquantes : {', '.join(missing)}")
        return False
    
    logger.info("✅ Variables d'environnement détectées.")
    return True

def step_2_scan_files():
    print_header("Étape 2 : Scan des fichiers CSV")
    csv_files = list(RAW_DIR.glob('*.csv'))
    
    if not csv_files:
        logger.warning("⚠️ Aucun fichier CSV trouvé dans le dossier raw.")
        logger.info("💡 Conseil : Déposez un fichier Apple Music dans ce dossier pour tester.")
        return []
    
    logger.info(f"✅ {len(csv_files)} fichier(s) trouvé(s) :")
    for f in csv_files:
        print(f"   - {f.name} ({f.stat().st_size / 1024:.2f} KB)")
    
    return csv_files

def step_3_test_parsing(files):
    print_header("Étape 3 : Test du Parsing (Détail)")
    parser = AppleMusicCSVParser()
    valid_data = []

    for file_path in files:
        print(f"\n📄 Analyse de : {file_path.name}")
        
        # 1. Test Encodage & Lecture brute
        df = None
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1']
        for enc in encodings:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                print(f"   ✅ Encodage réussi : {enc}")
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            logger.error("   ❌ Échec lecture : Aucun encodage ne fonctionne.")
            continue

        # 2. Inspection Colonnes
        print(f"   📋 Colonnes brutes : {list(df.columns)}")
        
        # 3. Exécution Parser
        result = parser.parse_csv_file(file_path)
        csv_type = result.get('type')
        data = result.get('data')

        if not csv_type:
            logger.error("   ❌ Type de CSV NON DÉTECTÉ.")
            print("   💡 Vérifiez le mapping dans 'apple_music_csv_parser.py'.")
        else:
            logger.info(f"   ✅ Type détecté : {csv_type}")
            logger.info(f"   📊 Lignes extraites : {len(data)}")
            
            if data:
                print(f"   🔎 Exemple de donnée (Ligne 1) :")
                print(f"      {data[0]}")
                valid_data.append((csv_type, data))
            else:
                logger.warning("   ⚠️ Aucune donnée extraite malgré le type détecté.")

    return valid_data

def step_4_database_dry_run(parsed_results):
    print_header("Étape 4 : Test BDD (Dry Run / Simulation)")
    
    if not parsed_results:
        logger.info("⏩ Pas de données à insérer. Fin du test.")
        return

    # Connexion BDD
    try:
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'localhost'), # Fallback localhost pour test hors docker
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        logger.info("✅ Connexion BDD établie.")
    except Exception as e:
        logger.error(f"❌ Échec connexion BDD : {e}")
        return

    # Simulation Insertion
    for csv_type, data in parsed_results:
        if csv_type == 'songs_performance':
            print(f"\n🔹 Simulation pour 'songs_performance' ({len(data)} lignes)")
            
            # A. Simulation Upsert Performance
            print("   [1] Table 'apple_songs_performance' (Upsert)")
            print(f"       Clé unique : song_name")
            print(f"       Colonnes à mettre à jour : album_name, plays, listeners...")
            
            # Vérification des doublons dans le CSV
            songs = [d['song_name'] for d in data]
            if len(songs) != len(set(songs)):
                logger.warning("       ⚠️ Attention : Doublons détectés dans le fichier source !")
            
            # B. Simulation Insert History
            print("   [2] Table 'apple_songs_history' (Snapshot)")
            print(f"       Date du snapshot : {datetime.now().date()}")
            
            # Vérification existence table
            try:
                res = db.fetch_df("SELECT count(*) FROM apple_songs_performance")
                print(f"       ℹ️  La table existe et contient déjà {res.iloc[0,0]} lignes.")
            except Exception as e:
                logger.warning(f"       ⚠️ La table n'existe peut-être pas : {e}")

    db.close()

if __name__ == "__main__":
    if step_1_check_environment():
        files = step_2_scan_files()
        if files:
            results = step_3_test_parsing(files)
            step_4_database_dry_run(results)
    
    print("\n✅ Debugging terminé.")