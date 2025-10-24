"""Collecte manuelle de popularité - Debug et test."""
import os
from dotenv import load_dotenv
from datetime import datetime
import psycopg2

load_dotenv()

def manual_collect():
    print("\n" + "="*70)
    print("🎸 COLLECTE MANUELLE POPULARITÉ SPOTIFY")
    print("="*70 + "\n")
    
    # 1. Test connexion Spotify
    print("1️⃣  Connexion Spotify API...")
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    
    auth_manager = SpotifyClientCredentials(
        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    print("   ✅ Connecté")
    
    # 2. Connexion PostgreSQL
    print("\n2️⃣  Connexion PostgreSQL (spotify_etl)...")
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='spotify_etl',
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    cursor = conn.cursor()
    print("   ✅ Connecté")
    
    # 3. Récupérer les artistes
    artist_ids = os.getenv('SPOTIFY_ARTIST_IDS', '').split(',')
    print(f"\n3️⃣  Artistes configurés : {len(artist_ids)}")
    
    total_inserted = 0
    
    for artist_id in artist_ids:
        artist_id = artist_id.strip()
        if not artist_id:
            continue
        
        print(f"\n📊 Traitement artiste : {artist_id}")
        
        # Infos artiste
        try:
            artist = sp.artist(artist_id)
            print(f"   ✅ Artiste : {artist['name']}")
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            continue
        
        # Top tracks
        try:
            results = sp.artist_top_tracks(artist_id, country='FR')
            tracks = results['tracks']
            print(f"   ✅ {len(tracks)} tracks récupérées")
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            continue
        
        # Insérer dans la base
        print(f"   💾 Insertion dans track_popularity_history...")
        
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        
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
        
        inserted = 0
        for track in tracks:
            try:
                cursor.execute(insert_query, (
                    track['id'],
                    track['name'],
                    track['popularity'],
                    current_datetime,
                    current_date
                ))
                inserted += 1
                print(f"      • {track['name']}: {track['popularity']}/100")
            except Exception as e:
                print(f"      ❌ Erreur pour {track['name']}: {e}")
        
        conn.commit()
        total_inserted += inserted
        print(f"   ✅ {inserted} tracks insérées")
    
    # 4. Vérification
    print(f"\n4️⃣  Vérification finale...")
    cursor.execute("""
        SELECT COUNT(*) 
        FROM track_popularity_history
        WHERE date = CURRENT_DATE
    """)
    count_today = cursor.fetchone()[0]
    print(f"   ✅ {count_today} enregistrements pour aujourd'hui")
    
    cursor.execute("""
        SELECT track_name, popularity, date
        FROM track_popularity_history
        ORDER BY collected_at DESC
        LIMIT 5
    """)
    
    print("\n📋 Derniers enregistrements :")
    for row in cursor.fetchall():
        print(f"   • {row[0]}: {row[1]}/100 (le {row[2]})")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    print(f"✅ COLLECTE TERMINÉE - {total_inserted} tracks insérées")
    print("="*70 + "\n")
    print("💡 Maintenant, rafraîchissez votre dashboard Streamlit !")

if __name__ == "__main__":
    manual_collect()