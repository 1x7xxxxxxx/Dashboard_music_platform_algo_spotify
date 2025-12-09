"""Script d'ingestion des CSV Meta Ads (Configuration)."""
import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup chemins
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
load_dotenv(project_root / '.env')

from src.transformers.meta_csv_parser import MetaCSVParser
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_ingestion():
    # 1. Dossier source
    raw_dir = project_root / 'data' / 'raw' / 'meta_ads' / 'configuration'
    csv_files = list(raw_dir.glob('*.csv'))
    
    if not csv_files:
        logger.warning(f"⚠️ Aucun fichier CSV trouvé dans {raw_dir}")
        return

    # 2. Connexion DB
    try:
        config = config_loader.load()
        db = PostgresHandler(**config['database'])
    except:
        # Fallback env vars
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', 5433)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )

    parser = MetaCSVParser()

    for csv_file in csv_files:
        logger.info(f"\n📄 Traitement de : {csv_file.name}")
        
        result = parser.parse_config_file(csv_file)
        
        if result:
            # 3. Ingestion Campagnes
            if not result['campaigns'].empty:
                logger.info(f"   📊 {len(result['campaigns'])} campagnes")
                db.upsert_many('meta_campaigns', result['campaigns'].to_dict('records'), 
                              ['campaign_id'], ['campaign_name', 'start_time', 'collected_at'])

            # 4. Ingestion AdSets
            if not result['adsets'].empty:
                logger.info(f"   📂 {len(result['adsets'])} adsets")
                db.upsert_many('meta_adsets', result['adsets'].to_dict('records'), 
                              ['adset_id'], ['adset_name', 'campaign_id', 'status', 'start_time', 'targeting', 'collected_at'])

            # 5. Ingestion Ads
            if not result['ads'].empty:
                logger.info(f"   📢 {len(result['ads'])} ads")
                # On s'assure d'avoir les colonnes minimales pour l'upsert
                ads_data = result['ads'].to_dict('records')
                db.upsert_many('meta_ads', ads_data, 
                              ['ad_id'], ['ad_name', 'adset_id', 'campaign_id', 'status', 'creative_id', 'collected_at'])
            
            logger.info("   ✅ Import terminé pour ce fichier.")
            
            # Optionnel : Déplacer dans processed
            # (processed_dir / csv_file.name).write_bytes(csv_file.read_bytes())
            # csv_file.unlink()

    db.close()
    logger.info("\n🏁 Fin de l'ingestion.")

if __name__ == "__main__":
    run_ingestion()