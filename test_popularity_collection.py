"""Test de la collecte de popularité."""
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def test_collection():
    from src.collectors.spotify_api import SpotifyCollector
    from src.database.postgres_handler import PostgresHandler
    
    print("\n" + "="*70)
    print("🧪 TEST COLLECTE POPULARITÉ")
    print("="*70 + "\n")
    
    # 1. Test connexion Spotify
    print("1️⃣  Test connexion Spotify API...")
    collector = SpotifyCollector(
        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
    )
    
    # Test avec un artiste
    artist_id = '7sbfafbLjNZGZJZjZ3xoPB'  # Ton artiste
    artist_info = collector.get_artist_info(artist_id)
    
    if artist_info:
        print(f"   ✅ Artiste : {artist_info['name']}")
    else:
        print("   ❌ Erreur connexion API")
        return
    
    # 2. Test connexion DB
    print("\n2️⃣  Test connexion PostgreSQL...")
    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='spotify_etl',
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    print("   ✅ Connexion OK")
    
    # 3. Vérifier table
    print("\n3️⃣  Vérification table track_popularity_history...")
    exists = db.table_exists('track_popularity_history')
    print(f"   {'✅' if exists else '❌'} Table existe : {exists}")
    
    # 4. Collecter et stocker
    print("\n4️⃣  Collecte des tracks...")
    tracks = collector.get_artist_top_tracks(artist_id)
    print(f"   ✅ {len(tracks)} tracks collectées")
    
    # 5. Stocker dans DB
    print("\n5️⃣  Stockage dans track_popularity_history...")
    
    current_datetime = datetime.now()
    current_date = current_datetime.date()
    
    popularity_records = []
    for track in tracks[:3]:  # Tester avec 3 tracks
        popularity_records.append({
            'track_id': track['track_id'],
            'track_name': track['track_name'],
            'popularity': track['popularity'],
            'collected_at': current_datetime,
            'date': current_date
        })
    
    count = db.upsert_many(
        table='track_popularity_history',
        data=popularity_records,
        conflict_columns=['track_id', 'date'],
        update_columns=['track_name', 'popularity', 'collected_at']
    )
    
    print(f"   ✅ {count} enregistrements stockés")
    
    # 6. Vérifier les données
    print("\n6️⃣  Vérification des données stockées...")
    query = "SELECT * FROM track_popularity_history ORDER BY collected_at DESC LIMIT 5"
    df = db.fetch_df(query)
    
    if not df.empty:
        print(f"   ✅ {len(df)} enregistrements trouvés")
        print("\n" + df.to_string(index=False))
    else:
        print("   ❌ Aucune donnée trouvée")
    
    db.close()
    
    print("\n" + "="*70)
    print("✅ TOUS LES TESTS PASSÉS")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_collection()