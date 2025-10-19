"""Correction du schéma Meta Ads - Augmentation taille des noms."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

def fix_meta_schema():
    """Augmente la taille des colonnes de noms."""
    print("\n" + "="*70)
    print("🔧 CORRECTION SCHÉMA META ADS")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # Modifications SQL
    modifications = [
        "ALTER TABLE meta_campaigns ALTER COLUMN campaign_name TYPE VARCHAR(500);",
        "ALTER TABLE meta_adsets ALTER COLUMN adset_name TYPE VARCHAR(500);",
        "ALTER TABLE meta_ads ALTER COLUMN ad_name TYPE VARCHAR(500);",
        "ALTER TABLE meta_ads ALTER COLUMN creative_id TYPE VARCHAR(100);"
    ]
    
    for sql in modifications:
        try:
            print(f"🔄 Exécution: {sql}")
            db.execute_query(sql)
            print(f"   ✅ OK")
        except Exception as e:
            print(f"   ⚠️ {e}")
    
    print("\n" + "="*70)
    print("✅ SCHÉMA CORRIGÉ")
    print("="*70 + "\n")
    
    db.close()

if __name__ == "__main__":
    fix_meta_schema()
