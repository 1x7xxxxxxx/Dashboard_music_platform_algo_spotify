"""Mise à jour du schéma Meta Ads pour optimisation."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

def update_meta_schema():
    """Ajoute les index pour optimiser les requêtes."""
    print("\n" + "="*70)
    print("🔧 MISE À JOUR SCHÉMA META ADS")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # Index pour optimiser les requêtes
    optimizations = [
        # Index composites pour les jointures fréquentes
        """
        CREATE INDEX IF NOT EXISTS idx_meta_insights_ad_date_perf 
        ON meta_insights(ad_id, date, conversions, spend);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign 
        ON meta_ads(campaign_id, ad_id);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_meta_adsets_campaign 
        ON meta_adsets(campaign_id, adset_id);
        """,
        
        # Index pour les filtres de date
        """
        CREATE INDEX IF NOT EXISTS idx_meta_insights_date_range 
        ON meta_insights(date DESC) WHERE conversions > 0;
        """,
        
        # Index pour les campagnes actives
        """
        CREATE INDEX IF NOT EXISTS idx_meta_campaigns_status 
        ON meta_campaigns(status, created_time DESC);
        """
    ]
    
    for i, sql in enumerate(optimizations, 1):
        try:
            print(f"🔄 [{i}/{len(optimizations)}] Création index...")
            db.execute_query(sql)
            print(f"   ✅ OK")
        except Exception as e:
            print(f"   ⚠️ {e}")
    
    print("\n" + "="*70)
    print("✅ SCHÉMA OPTIMISÉ")
    print("="*70 + "\n")
    
    db.close()

if __name__ == "__main__":
    update_meta_schema()