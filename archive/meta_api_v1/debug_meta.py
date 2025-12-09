import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv  # <--- AJOUT CRUCIAL

# Setup des chemins
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Chargement du .env (C'est ça qui manquait !)
load_dotenv(project_root / '.env')

from src.utils.config_loader import config_loader
from src.collectors.meta_ads_collector import MetaAdsCollector
from src.database.postgres_handler import PostgresHandler

# Config logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_meta_ingestion():
    print("\n" + "="*60)
    print("🐞 DEBUG META ADS INGESTION (Code Réel)")
    print("="*60)

    # 1. Config
    try:
        # On force la lecture des variables d'env
        app_id = os.getenv('META_APP_ID')
        access_token = os.getenv('META_ACCESS_TOKEN')
        ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        app_secret = os.getenv('META_APP_SECRET')
        
        print(f"🔑 App ID: {app_id}")
        print(f"📺 Account ID: {ad_account_id}")
        if access_token:
            print(f"🎟️ Token: {access_token[:10]}...")
        else:
            print("❌ Token manquant !")
            return

    except Exception as e:
        print(f"❌ Erreur Config: {e}")
        return

    # 2. Initialisation Collector
    try:
        collector = MetaAdsCollector(
            app_id=app_id,
            app_secret=app_secret,
            access_token=access_token,
            ad_account_id=ad_account_id
        )
        print("✅ Collector initialisé.")
    except Exception as e:
        print(f"❌ Erreur Init Collector: {e}")
        return

    # 3. Test de récupération
    print("\n📡 Test 1 : Récupération des campagnes...")
    try:
        all_campaigns = collector.get_campaigns() 
        print(f"📦 Campagnes trouvées : {len(all_campaigns)}")
        
        if all_campaigns:
            print("👀 Statuts trouvés :")
            for c in all_campaigns[:5]:
                print(f"   - {c.get('name')} [{c.get('status')}]")
        else:
            print("⚠️ Aucune campagne trouvée. Vérifiez le compte pub.")

    except Exception as e:
        print(f"❌ Erreur Fetch: {e}")
        return

    # 4. Test Insertion BDD
    if all_campaigns:
        print("\n💾 Test 2 : Insertion en base...")
        try:
            # On charge la config DB depuis config.yaml ou env
            try:
                config = config_loader.load()
                db_config = config['database']
            except:
                # Fallback sur env si config.yaml n'existe pas
                db_config = {
                    'host': os.getenv('DATABASE_HOST', 'localhost'),
                    'port': int(os.getenv('DATABASE_PORT', 5433)),
                    'database': os.getenv('DATABASE_NAME', 'spotify_etl'),
                    'user': os.getenv('DATABASE_USER', 'postgres'),
                    'password': os.getenv('DATABASE_PASSWORD')
                }

            db = PostgresHandler(**db_config)
            count = db.upsert_many(
                table='meta_campaigns',
                data=all_campaigns,
                conflict_columns=['campaign_id'],
                update_columns=['campaign_name', 'status', 'objective', 'daily_budget', 'lifetime_budget', 'collected_at']
            )
            print(f"✅ {count} campagnes insérées dans 'meta_campaigns'.")
            db.close()
        except Exception as e:
            print(f"❌ Erreur SQL: {e}")

if __name__ == "__main__":
    debug_meta_ingestion()