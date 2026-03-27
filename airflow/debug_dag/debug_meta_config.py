"""
🐛 DEBUGGER ULTIME - META ADS CONFIGURATION
Ce script teste isolément chaque étape du processus d'import de configuration Meta :
1. Variables d'environnement (.env)
2. Scan du dossier 'data/raw/meta_ads/configuration'
3. Parsing du fichier (MetaCSVParser)
4. Connexion BDD
5. Simulation d'insertion SQL (Dry Run)
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- Configuration Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("MetaConfigDebug")

# --- Chargement Environnement ---
load_dotenv()

# Ajout du chemin pour importer vos modules
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Imports conditionnels
try:
    from src.database.postgres_handler import PostgresHandler
    from src.transformers.meta_csv_parser import MetaCSVParser
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Erreur d'import critique : {e}")
    logger.error("Vérifiez que vous êtes à la racine du projet.")
    MODULES_AVAILABLE = False

# Chemins
RAW_DIR = project_root / "data" / "raw" / "meta_ads" / "configuration"

def print_header(title):
    print(f"\n{'='*60}")
    print(f"📘  {title.upper()}")
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
        logger.warning("⚠️ Aucun fichier de config (CSV/XLSX) trouvé.")
        logger.info("💡 Action : Déposez un fichier d'export Meta dans 'data/raw/meta_ads/configuration'")
        return []
    
    logger.info(f"✅ {len(files)} fichier(s) trouvé(s) :")
    for f in files:
        print(f"   - {f}")
    
    return files

def step_3_test_parsing(files):
    print_header("Étape 3 : Test Parsing (MetaCSVParser)")
    parser = MetaCSVParser()
    valid_data = []

    for filename in files:
        file_path = RAW_DIR / filename
        print(f"\n📄 Analyse de : {filename}")
        
        try:
            result = parser.parse(file_path)
            
            if not result or not result.get('data'):
                logger.error("   ❌ Parsing échoué ou aucune donnée retournée.")
                continue
                
            data = result['data']
            c_len = len(data.get('campaigns', []))
            as_len = len(data.get('adsets', []))
            ad_len = len(data.get('ads', []))
            
            if c_len + as_len + ad_len == 0:
                logger.warning("   ⚠️ Fichier lu mais aucune ligne valide extraite.")
            else:
                logger.info("   ✅ Extraction réussie :")
                logger.info(f"      - Campagnes : {c_len}")
                logger.info(f"      - AdSets    : {as_len}")
                logger.info(f"      - Ads       : {ad_len}")
                
                # Aperçu des données (pour vérifier le mapping)
                if c_len > 0:
                    print(f"      🔎 Exemple Campagne : {data['campaigns'][0]}")
                if as_len > 0:
                    print(f"      🔎 Exemple AdSet : {data['adsets'][0].keys()}") # Juste les clés pour pas inonder

                valid_data.append(data)
                
        except Exception as e:
            logger.error(f"   ❌ Exception lors du parsing : {e}")

    return valid_data

def step_4_dry_run_db(parsed_data_list):
    print_header("Étape 4 : Test BDD & Simulation Insertion")
    
    if not parsed_data_list:
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

    # Simulation
    for i, data in enumerate(parsed_data_list):
        print(f"\n🔹 Simulation Fichier #{i+1}")
        
        c_list = data.get('campaigns', [])
        as_list = data.get('adsets', [])
        ad_list = data.get('ads', [])

        # Campagnes
        if c_list:
            print(f"   [Campagnes] {len(c_list)} lignes prêtes.")
            print("   📝 Requête SQL type :")
            print("""
            INSERT INTO meta_campaigns (campaign_id, campaign_name, start_time)
            VALUES (%(campaign_id)s, %(campaign_name)s, %(start_time)s)
            ON CONFLICT (campaign_id) DO UPDATE ...
            """)

        # AdSets
        if as_list:
            print(f"   [AdSets] {len(as_list)} lignes prêtes.")
            # Vérif d'intégrité rapide
            missing_parents = [a for a in as_list if a['campaign_id'] not in [c['campaign_id'] for c in c_list]]
            if missing_parents:
                logger.warning(f"      ⚠️ Attention : {len(missing_parents)} AdSets font référence à des campagnes non présentes dans ce fichier.")
            
        # Ads
        if ad_list:
            print(f"   [Ads] {len(ad_list)} lignes prêtes.")

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