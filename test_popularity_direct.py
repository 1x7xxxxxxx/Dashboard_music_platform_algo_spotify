# test_popularity_direct.py
import os
from dotenv import load_dotenv
from datetime import datetime, date
import psycopg2

load_dotenv()

def test_direct():
    print("\n" + "="*70)
    print("🧪 TEST DIRECT COLLECTE POPULARITÉ")
    print("="*70 + "\n")
    
    # 1. Test connexion à spotify_etl
    print("1️⃣  Connexion à PostgreSQL (spotify_etl)...")
    try:
        conn = psycopg2.connect(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', 5433)),
            database='spotify_etl',
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        cursor = conn.cursor()
        print("   ✅ Connecté à spotify_etl")
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
        return
    
    # 2. Vérifier que la table existe
    print("\n2️⃣  Vérification table track_popularity_history...")
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'track_popularity_history'
        );
    """)
    exists = cursor.fetchone()[0]
    print(f"   {'✅' if exists else '❌'} Table existe : {exists}")
    
    if not exists:
        print("\n   ⚠️  Création de la table...")
        cursor.execute("""
            CREATE TABLE track_popularity_history (
                id SERIAL PRIMARY KEY,
                track_id VARCHAR(50) NOT NULL,
                track_name VARCHAR(255) NOT NULL,
                popularity INTEGER DEFAULT 0,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date DATE DEFAULT CURRENT_DATE,
                UNIQUE(track_id, date)
            );
            
            CREATE INDEX IF NOT EXISTS idx_track_pop_history_track 
            ON track_popularity_history(track_id);
            
            CREATE INDEX IF NOT EXISTS idx_track_pop_history_date 
            ON track_popularity_history(date DESC);
        """)
        conn.commit()
        print("   ✅ Table créée")
    
    # 3. Test collecte Spotify
    print("\n3️⃣  Test collecte Spotify API...")
    from src.collectors.spotify_api import SpotifyCollector
    
    collector = SpotifyCollector(
        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
    )
    
    artist_id = os.getenv('SPOTIFY_ARTIST_IDS', '').split(',')[0].strip()
    print(f"   🎸 Artiste ID: {artist_id}")
    
    artist_info = collector.get_artist_info(artist_id)
    if artist_info:
        print(f"   ✅ Artiste: {artist_info['name']}")
    else:
        print("   ❌ Échec récupération artiste")
        cursor.close()
        conn.close()
        return
    
    tracks = collector.get_artist_top_tracks(artist_id)
    print(f"   ✅ {len(tracks)} tracks récupérées")
    
    # 4. Insertion manuelle
    print("\n4️⃣  Insertion dans track_popularity_history...")
    
    current_datetime = datetime.now()
    current_date = date.today()
    
    insert_query = """
        INSERT INTO track_popularity_history 
        (track_id, track_name, popularity, collected_at, date)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (track_id, date) 
        DO UPDATE SET 
            track_name = EXCLUDED.track_name,
            popularity = EXCLUDED.popularity,
            collected_at = EXCLUDED.collected_at
    """
    
    count = 0
    for track in tracks[:3]:  # Test avec 3 tracks
        cursor.execute(insert_query, (
            track['track_id'],
            track['track_name'],
            track['popularity'],
            current_datetime,
            current_date
        ))
        count += 1
        print(f"   • {track['track_name']}: {track['popularity']}/100")
    
    conn.commit()
    print(f"\n   ✅ {count} enregistrements insérés")
    
    # 5. Vérification
    print("\n5️⃣  Vérification des données...")
    cursor.execute("""
        SELECT track_name, popularity, date, collected_at
        FROM track_popularity_history
        ORDER BY collected_at DESC
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"   ✅ {len(rows)} enregistrements trouvés :")
        for row in rows:
            print(f"      • {row[0]}: {row[1]}/100 (le {row[2]})")
    else:
        print("   ❌ Aucune donnée trouvée")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ TEST TERMINÉ")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_direct()