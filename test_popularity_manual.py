# Crée ce fichier : test_popularity_manual.py
import os
from dotenv import load_dotenv
from datetime import datetime, date

load_dotenv()

def test_manual_collection():
    from src.collectors.spotify_api import SpotifyCollector
    from src.database.postgres_handler import PostgresHandler
    
    print("\n" + "="*70)
    print("🧪 TEST MANUEL COLLECTE POPULARITÉ")
    print("="*70 + "\n")
    
    # 1. Connexion Spotify
    print("1️⃣  Connexion Spotify API...")
    collector = SpotifyCollector(
        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
    )
    print("   ✅ Connecté")
    
    # 2. Connexion PostgreSQL
    print("\n2️⃣  Connexion PostgreSQL...")
    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='spotify_etl',  # ✅ Base correcte
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    print("   ✅ Connecté")
    
    # 3. Récupérer les artistes depuis .env
    artist_ids = os.getenv('SPOTIFY_ARTIST_IDS', '').split(',')
    print(f"\n3️⃣  Artistes configurés : {len(artist_ids)}")
    
    for artist_id in artist_ids:
        artist_id = artist_id.strip()
        if not artist_id:
            continue
        
        print(f"\n📊 Traitement artiste : {artist_id}")
        
        # Récupérer infos artiste
        artist_info = collector.get_artist_info(artist_id)
        if not artist_info:
            print(f"   ❌ Erreur récupération artiste")
            continue
        
        print(f"   ✅ Artiste : {artist_info['name']}")
        
        # Récupérer top tracks
        tracks = collector.get_artist_top_tracks(artist_id)
        print(f"   ✅ {len(tracks)} tracks récupérées")
        
        # Préparer les données de popularité
        current_datetime = datetime.now()
        current_date = date.today()  # ✅ Maintenant correctement importé
        
        popularity_records = []
        for track in tracks:
            popularity_records.append({
                'track_id': track['track_id'],
                'track_name': track['track_name'],
                'popularity': track['popularity'],
                'collected_at': current_datetime,
                'date': current_date
            })
        
        # Stocker dans la base
        print(f"   💾 Stockage de {len(popularity_records)} enregistrements...")
        
        count = db.upsert_many(
            table='track_popularity_history',
            data=popularity_records,
            conflict_columns=['track_id', 'date'],
            update_columns=['track_name', 'popularity', 'collected_at']
        )
        
        print(f"   ✅ {count} enregistrements stockés")
        
        # Afficher les données
        for record in popularity_records[:3]:
            print(f"      • {record['track_name']}: {record['popularity']}/100")
    
    db.close()
    
    print("\n" + "="*70)
    print("✅ TEST TERMINÉ")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_manual_collection()