"""Création des tables PostgreSQL pour Meta Ads."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.database.meta_ads_schema import META_ADS_SCHEMA
from src.utils.config_loader import config_loader


def create_meta_tables():
    """Crée toutes les tables Meta Ads."""
    print("\n" + "="*70)
    print("🗄️ CRÉATION DES TABLES META ADS")
    print("="*70)
    
    # Connexion
    config = config_loader.load()
    db_config = config['database']
    
    db = PostgresHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )
    
    print(f"✅ Connecté à PostgreSQL ({db_config['database']})")
    
    # Créer chaque table
    for table_name, create_sql in META_ADS_SCHEMA.items():
        print(f"\n📋 Création de la table '{table_name}'...")
        try:
            db.execute_query(create_sql)
            count = db.get_table_count(table_name)
            print(f"✅ Table '{table_name}' créée avec succès")
            print(f"   📊 Lignes actuelles : {count}")
        except Exception as e:
            print(f"❌ Erreur : {e}")
    
    db.close()
    
    print("\n" + "="*70)
    print("✅ TABLES META ADS CRÉÉES AVEC SUCCÈS")
    print("="*70)
    print("\n🔜 Prochaine étape : Créer le collector Meta Ads")
    print("   Commande : python collect_meta_ads.py")


if __name__ == "__main__":
    create_meta_tables()