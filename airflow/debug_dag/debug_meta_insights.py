"""
🐛 DEBUGGER ULTIME - META ADS INSIGHTS
Ce script teste isolément chaque étape du processus d'import des Insights Meta :
1. Variables d'environnement (.env)
2. Scan du dossier 'data/raw/meta_ads/insights'
3. Parsing Intelligent (Détection Auto : Performance vs Engagement + Breakdown)
4. Connexion BDD
5. Simulation d'insertion SQL (Dry Run) avec vérification des colonnes
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# --- Configuration Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("MetaInsightsDebug")

# --- Chargement Environnement ---
load_dotenv()

# Ajout du chemin pour importer vos modules
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Imports conditionnels
try:
    from src.database.postgres_handler import PostgresHandler
    from src.transformers.meta_insight_csv_parser import MetaInsightParser
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Erreur d'import critique : {e}")
    logger.error("Vérifiez que vous êtes à la racine du projet.")
    MODULES_AVAILABLE = False

# Chemins
RAW_DIR = project_root / "data" / "raw" / "meta_ads" / "insights"

def print_header(title):
    print(f"\n{'='*60}")
    print(f"📊  {title.upper()}")
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
    files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.csv', '.xlsx'))]
    
    if not files:
        logger.warning("⚠️ Aucun fichier d'insight (CSV/XLSX) trouvé.")
        logger.info("💡 Action : Déposez un fichier (ex: Age, Country, Engagement) dans 'data/raw/meta_ads/insights'")
        return []
    
    logger.info(f"✅ {len(files)} fichier(s) trouvé(s) :")
    for f in files:
        print(f"   - {f}")
    
    return files

def step_3_test_parsing(files):
    print_header("Étape 3 : Test Parsing Intelligent")
    parser = MetaInsightParser()
    valid_data = []

    for filename in files:
        file_path = RAW_DIR / filename
        print(f"\n📄 Analyse de : {filename}")
        
        try:
            # 1. Lecture Brute pour Debug Headers
            df_raw = parser.read_flexible(file_path)
            if not df_raw.empty:
                # Aperçu rapide des premières lignes pour aider l'utilisateur
                print(f"      👀 Aperçu (Ligne 0-2) :")
                for i in range(min(3, len(df_raw))):
                    print(f"         {list(df_raw.iloc[i].values)[:4]} ...")
            
            # 2. Parsing Réel
            result = parser.parse_csv(file_path)
            ftype = result.get('type')
            data = result.get('data')

            if ftype == 'error' or not data:
                logger.error(f"   ❌ Échec Parsing : Type '{ftype}' / Data vide.")
                continue

            logger.info(f"   ✅ Type détecté : {ftype.upper()}")
            logger.info(f"   📊 Lignes extraites : {len(data)}")
            
            # Inspection d'un échantillon
            sample = data[0]
            print(f"      🔎 Echantillon :")
            # Affichage sélectif des clés non-nulles
            for k, v in sample.items():
                if v: print(f"         - {k}: {v}")

            valid_data.append((ftype, data))
                
        except Exception as e:
            logger.error(f"   ❌ Exception Parser : {e}")

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
        
        # Détermination de la table cible
        table_suffix = ftype.replace("performance_", "").replace("engagement_", "")
        if table_suffix == "global":
            table_name = f"meta_insights_{ftype.split('_')[0]}" # meta_insights_performance ou meta_insights_engagement
        else:
            table_name = f"meta_insights_{ftype}"

        print(f"   🎯 Table Cible : {table_name}")
        
        # Vérification des colonnes manquantes (Simulation stricte)
        sample = data[0]
        missing_keys = [k for k, v in sample.items() if v is None]
        if missing_keys:
            logger.warning(f"      ⚠️ Attention, champs NULL trouvés : {missing_keys}")
        
        # Construction SQL théorique
        print("   📝 Requête SQL simulée :")
        if "performance" in ftype:
            print(f"""
            INSERT INTO {table_name} (campaign_name, spend, results, ...)
            VALUES ('{sample.get('campaign_name')}', {sample.get('spend')}, ...)
            ON CONFLICT (...) DO UPDATE ...
            """)
        elif "engagement" in ftype:
            print(f"""
            INSERT INTO {table_name} (campaign_name, post_reactions, comments, ...)
            VALUES ('{sample.get('campaign_name')}', {sample.get('post_reactions')}, ...)
            ON CONFLICT (...) DO UPDATE ...
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