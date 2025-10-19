"""Script de collecte et stockage Meta Ads vers PostgreSQL."""
import sys
from pathlib import Path
from datetime import datetime
import logging
import json

sys.path.append(str(Path(__file__).parent))

from src.collectors.meta_ads_collector import MetaAdsCollector
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

# Configuration du logging
Path('logs').mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/meta_ads_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MetaAdsETL:
    """ETL complet pour Meta Ads."""
    
    def __init__(self):
        """Initialise l'ETL."""
        self.config = config_loader.load()
        self.meta_config = self.config['meta_ads']
        self.db_config = self.config['database']
        
        # Initialiser collector
        self.collector = MetaAdsCollector(
            app_id=self.meta_config['app_id'],
            app_secret=self.meta_config['app_secret'],
            access_token=self.meta_config['access_token'],
            ad_account_id=self.meta_config['ad_account_id'],
            api_version=self.meta_config.get('api_version', 'v21.0')
        )
        
        # Initialiser base de données
        self.db = PostgresHandler(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )
    
    def collect_data(self, days_insights: int = 30):
        """Collecte les données depuis Meta Ads."""
        logger.info("="*70)
        logger.info("🚀 DÉBUT COLLECTE META ADS")
        logger.info("="*70)
        
        try:
            data = self.collector.collect_all(days_insights=days_insights)
            
            logger.info(f"✅ Collecte terminée:")
            logger.info(f"   📊 Campagnes : {len(data['campaigns'])}")
            logger.info(f"   📊 Adsets    : {len(data['adsets'])}")
            logger.info(f"   📊 Ads       : {len(data['ads'])}")
            logger.info(f"   📊 Insights  : {len(data['insights'])}")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la collecte: {e}")
            raise
    
    def transform_data(self, data: dict):
        """Transforme les données pour PostgreSQL."""
        logger.info("\n🔄 TRANSFORMATION DES DONNÉES")
        
        transformed = {
            'campaigns': data['campaigns'],
            'adsets': [],
            'ads': data['ads'],
            'insights': data['insights']
        }
        
        # Transformer adsets - convertir targeting en JSON
        for adset in data['adsets']:
            adset_copy = adset.copy()
            
            # Convertir le targeting en JSON string si c'est un objet
            if 'targeting' in adset_copy and adset_copy['targeting'] is not None:
                if not isinstance(adset_copy['targeting'], str):
                    try:
                        adset_copy['targeting'] = json.dumps(adset_copy['targeting'])
                    except Exception as e:
                        logger.warning(f"⚠️ Impossible de convertir targeting: {e}")
                        adset_copy['targeting'] = None
            
            transformed['adsets'].append(adset_copy)
        
        logger.info("✅ Transformation terminée")
        return transformed
    
    def load_to_database(self, data: dict):
        """Charge les données dans PostgreSQL."""
        logger.info("\n💾 CHARGEMENT VERS POSTGRESQL")
        
        stats = {
            'campaigns': 0,
            'adsets': 0,
            'ads': 0,
            'insights': 0
        }
        
        try:
            # 1. Upsert Campaigns
            if data['campaigns']:
                logger.info(f"📊 Insertion de {len(data['campaigns'])} campagnes...")
                stats['campaigns'] = self.db.upsert_many(
                    table='meta_campaigns',
                    data=data['campaigns'],
                    conflict_columns=['campaign_id'],
                    update_columns=[
                        'campaign_name', 'status', 'objective',
                        'daily_budget', 'lifetime_budget',
                        'updated_time', 'collected_at'
                    ]
                )
                logger.info(f"   ✅ {stats['campaigns']} campagnes traitées")
            
            # 2. Upsert Adsets
            if data['adsets']:
                logger.info(f"📊 Insertion de {len(data['adsets'])} adsets...")
                stats['adsets'] = self.db.upsert_many(
                    table='meta_adsets',
                    data=data['adsets'],
                    conflict_columns=['adset_id'],
                    update_columns=[
                        'adset_name', 'status', 'optimization_goal',
                        'billing_event', 'daily_budget', 'lifetime_budget',
                        'targeting', 'collected_at'
                    ]
                )
                logger.info(f"   ✅ {stats['adsets']} adsets traités")
            
            # 3. Upsert Ads
            if data['ads']:
                logger.info(f"📊 Insertion de {len(data['ads'])} ads...")
                stats['ads'] = self.db.upsert_many(
                    table='meta_ads',
                    data=data['ads'],
                    conflict_columns=['ad_id'],
                    update_columns=[
                        'ad_name', 'status', 'creative_id',
                        'updated_time', 'collected_at'
                    ]
                )
                logger.info(f"   ✅ {stats['ads']} ads traitées")
            
            # 4. Upsert Insights
            if data['insights']:
                logger.info(f"📊 Insertion de {len(data['insights'])} insights...")
                stats['insights'] = self.db.upsert_many(
                    table='meta_insights',
                    data=data['insights'],
                    conflict_columns=['ad_id', 'date'],
                    update_columns=[
                        'impressions', 'clicks', 'spend', 'reach',
                        'frequency', 'cpc', 'cpm', 'ctr',
                        'conversions', 'cost_per_conversion', 'collected_at'
                    ]
                )
                logger.info(f"   ✅ {stats['insights']} insights traités")
            
            logger.info("✅ Chargement terminé avec succès")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement: {e}")
            raise
    
    def run_etl(self, days_insights: int = 30):
        """Exécute le pipeline ETL complet."""
        start_time = datetime.now()
        
        logger.info("\n" + "="*70)
        logger.info("🎯 DÉMARRAGE ETL META ADS → POSTGRESQL")
        logger.info("="*70)
        
        try:
            # EXTRACT
            raw_data = self.collect_data(days_insights=days_insights)
            
            # TRANSFORM
            transformed_data = self.transform_data(raw_data)
            
            # LOAD
            stats = self.load_to_database(transformed_data)
            
            # Résumé
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info("\n" + "="*70)
            logger.info("✅ ETL TERMINÉ AVEC SUCCÈS")
            logger.info("="*70)
            logger.info(f"⏱️  Durée totale: {duration:.2f}s")
            logger.info(f"📊 Statistiques:")
            logger.info(f"   • Campagnes : {stats['campaigns']} traitées")
            logger.info(f"   • Adsets    : {stats['adsets']} traités")
            logger.info(f"   • Ads       : {stats['ads']} traitées")
            logger.info(f"   • Insights  : {stats['insights']} traités")
            logger.info("="*70 + "\n")
            
            return {
                'success': True,
                'duration': duration,
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"\n❌ ETL ÉCHOUÉ: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        
        finally:
            self.db.close()


def main():
    """Point d'entrée principal."""
    # Lancer l'ETL
    etl = MetaAdsETL()
    
    # Collecter 30 derniers jours d'insights par défaut
    result = etl.run_etl(days_insights=30)
    
    if result['success']:
        print("\n🎉 ETL Meta Ads terminé avec succès !")
        print(f"📊 Consultez les logs: logs/meta_ads_collection.log")
    else:
        print(f"\n❌ ETL échoué: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()