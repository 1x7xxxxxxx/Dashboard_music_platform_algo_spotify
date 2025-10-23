"""Création de la table track_popularity_history."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from spotify_schema import SPOTIFY_SCHEMA
from src.utils.config_loader import config_loader


def create_track_popularity_table():
    """Crée la table track_popularity_history."""
    print("\n" + "="*70)
    print("📊 CRÉATION TABLE TRACK_POPULARITY_HISTORY")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    try:
        # Créer la table
        print("🔄 Création de la table track_popularity_history...")
        db.execute_query(SPOTIFY_SCHEMA['track_popularity_history'])
        print("   ✅ Table créée avec succès")
        
        # Vérifier la structure
        verify_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'track_popularity_history'
            ORDER BY ordinal_position;
        """
        
        df_structure = db.fetch_df(verify_query)
        
        print("\n📋 Structure de la table :")
        print("-" * 70)
        print(df_structure.to_string(index=False))
        
        # Compter les lignes existantes
        count = db.get_table_count('track_popularity_history')
        print(f"\n📊 Enregistrements actuels : {count}")
        
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        return False
    
    print("\n" + "="*70)
    print("✅ TABLE CRÉÉE AVEC SUCCÈS")
    print("="*70 + "\n")
    
    db.close()
    return True


if __name__ == "__main__":
    create_track_popularity_table()