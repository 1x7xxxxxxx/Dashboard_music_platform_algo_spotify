"""Vérification des données de popularité."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

def check_popularity_data():
    print("\n" + "="*70)
    print("🔍 VÉRIFICATION DONNÉES POPULARITÉ")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # 1. Vérifier l'existence de la table
    table_exists = db.table_exists('track_popularity_history')
    print(f"📋 Table 'track_popularity_history' existe : {'✅ OUI' if table_exists else '❌ NON'}")
    
    if not table_exists:
        print("\n⚠️  La table n'existe pas. Créez-la avec :")
        print("   python create_track_popularity_table.py")
        db.close()
        return
    
    # 2. Compter les enregistrements
    count = db.get_table_count('track_popularity_history')
    print(f"📊 Enregistrements totaux : {count:,}")
    
    if count == 0:
        print("\n⚠️  Aucune donnée trouvée. Lancez la collecte Spotify API.")
        db.close()
        return
    
    # 3. Afficher les dernières données
    query = """
        SELECT 
            track_name,
            popularity,
            date,
            collected_at
        FROM track_popularity_history
        ORDER BY collected_at DESC
        LIMIT 10
    """
    
    df = db.fetch_df(query)
    
    print("\n📊 Dernières 10 entrées :")
    print("-" * 70)
    print(df.to_string(index=False))
    
    # 4. Vérifier la plage de dates
    date_range_query = """
        SELECT 
            MIN(date) as first_date,
            MAX(date) as last_date,
            COUNT(DISTINCT track_name) as unique_tracks,
            COUNT(*) as total_records
        FROM track_popularity_history
    """
    
    df_range = db.fetch_df(date_range_query)
    
    print("\n📅 Plage de dates :")
    print("-" * 70)
    print(df_range.to_string(index=False))
    
    # 5. Tracks disponibles
    tracks_query = """
        SELECT 
            track_name,
            COUNT(*) as data_points,
            MIN(date) as first_date,
            MAX(date) as last_date,
            MAX(popularity) as max_pop
        FROM track_popularity_history
        GROUP BY track_name
        ORDER BY data_points DESC
    """
    
    df_tracks = db.fetch_df(tracks_query)
    
    print("\n🎵 Tracks avec historique :")
    print("-" * 70)
    print(df_tracks.to_string(index=False))
    
    print("\n" + "="*70)
    print("✅ VÉRIFICATION TERMINÉE")
    print("="*70 + "\n")
    
    db.close()

if __name__ == "__main__":
    check_popularity_data()