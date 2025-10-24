"""Diagnostic complet du problème de popularité."""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def diagnose():
    print("\n" + "="*70)
    print("🔍 DIAGNOSTIC COMPLET - POPULARITÉ SPOTIFY")
    print("="*70 + "\n")
    
    # 1. Vérifier les credentials
    print("1️⃣  CREDENTIALS SPOTIFY")
    print("-" * 70)
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    artist_ids = os.getenv('SPOTIFY_ARTIST_IDS')
    
    print(f"   CLIENT_ID     : {'✅ Présent' if client_id else '❌ Manquant'}")
    print(f"   CLIENT_SECRET : {'✅ Présent' if client_secret else '❌ Manquant'}")
    print(f"   ARTIST_IDS    : {artist_ids if artist_ids else '❌ Manquant'}")
    
    # 2. Vérifier la connexion PostgreSQL
    print("\n2️⃣  CONNEXION POSTGRESQL")
    print("-" * 70)
    
    try:
        # Connexion à airflow_db
        conn_airflow = psycopg2.connect(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', 5433)),
            database='airflow_db',
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        cursor_airflow = conn_airflow.cursor()
        print(f"   airflow_db    : ✅ Connexion OK")
        
        # Vérifier si la table existe dans airflow_db
        cursor_airflow.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'track_popularity_history'
            );
        """)
        exists_airflow = cursor_airflow.fetchone()[0]
        print(f"   Table dans airflow_db : '✅ Existe' if exists_airflow else '❌ N'existe pas'")


        
        if exists_airflow:
            cursor_airflow.execute("SELECT COUNT(*) FROM track_popularity_history")
            count_airflow = cursor_airflow.fetchone()[0]
            print(f"   Enregistrements : {count_airflow}")
        
        cursor_airflow.close()
        conn_airflow.close()
        
    except Exception as e:
        print(f"   ❌ Erreur airflow_db : {e}")
    
    try:
        # Connexion à spotify_etl
        conn_spotify = psycopg2.connect(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', 5433)),
            database='spotify_etl',
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        cursor_spotify = conn_spotify.cursor()
        print(f"\n   spotify_etl   : ✅ Connexion OK")
        
        # Vérifier si la table existe dans spotify_etl
        cursor_spotify.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'track_popularity_history'
            );
        """)
        exists_spotify = cursor_spotify.fetchone()[0]
        print(f"   Table dans spotify_etl : '✅ Existe' if exists_spotify else '❌ N'existe pas'")
        
        if exists_spotify:
            cursor_spotify.execute("SELECT COUNT(*) FROM track_popularity_history")
            count_spotify = cursor_spotify.fetchone()[0]
            print(f"   Enregistrements : {count_spotify}")
            
            if count_spotify > 0:
                cursor_spotify.execute("""
                    SELECT track_name, popularity, date, collected_at
                    FROM track_popularity_history
                    ORDER BY collected_at DESC
                    LIMIT 3
                """)
                
                print(f"\n   📋 Derniers enregistrements :")
                for row in cursor_spotify.fetchall():
                    print(f"      • {row[0]}: {row[1]}/100 (le {row[2]})")
        
        cursor_spotify.close()
        conn_spotify.close()
        
    except Exception as e:
        print(f"   ❌ Erreur spotify_etl : {e}")
    
    # 3. Tester l'API Spotify
    print("\n3️⃣  API SPOTIFY")
    print("-" * 70)
    
    if not client_id or not client_secret:
        print("   ❌ Credentials manquants")
    else:
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            
            auth_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret
            )
            sp = spotipy.Spotify(auth_manager=auth_manager)
            
            # Test avec Daft Punk
            test_artist = sp.artist('4tZwfgrHOc3mvqYlEYSvVi')
            print(f"   ✅ Connexion API OK")
            print(f"   ✅ Test : {test_artist['name']}")
            
            # Test avec vos artistes
            if artist_ids:
                for artist_id in artist_ids.split(',')[:1]:  # Tester le premier
                    artist_id = artist_id.strip()
                    if artist_id:
                        try:
                            artist = sp.artist(artist_id)
                            results = sp.artist_top_tracks(artist_id, country='FR')
                            tracks_count = len(results['tracks'])
                            print(f"   ✅ Votre artiste : {artist['name']} ({tracks_count} tracks)")
                        except Exception as e:
                            print(f"   ❌ Erreur artiste {artist_id}: {e}")
        
        except Exception as e:
            print(f"   ❌ Erreur API : {e}")
    
    # 4. Vérifier le DAG
    print("\n4️⃣  DAG SPOTIFY_API_DAILY")
    print("-" * 70)
    
    dag_path = "airflow/dags/spotify_api_daily.py"
    if os.path.exists(dag_path):
        print(f"   ✅ DAG trouvé : {dag_path}")
        
        with open(dag_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Vérifier les imports critiques
            has_date_import = "from datetime import datetime, timedelta, date" in content or "import datetime" in content
            has_popularity_section = "track_popularity_history" in content
            
            print(f"   {'✅' if has_date_import else '⚠️ '} Import datetime.date")
            print(f"   {'✅' if has_popularity_section else '❌'} Section popularité")
    else:
        print(f"   ❌ DAG non trouvé : {dag_path}")
    
    # 5. Résumé et recommandations
    print("\n" + "="*70)
    print("📊 RÉSUMÉ ET RECOMMANDATIONS")
    print("="*70)
    
    print("\n💡 Pour résoudre le problème :")
    print("   1. Assurez-vous que la table existe dans 'spotify_etl'")
    print("      → Lancez : python verify_and_fix_popularity_table.py")
    print("")
    print("   2. Testez la collecte manuelle")
    print("      → Lancez : python manual_popularity_collect.py")
    print("")
    print("   3. Si succès, vérifiez le dashboard")
    print("      → Rafraîchissez Streamlit")
    print("")
    print("   4. Vérifiez que le DAG utilise la bonne base")
    print("      → Le DAG doit se connecter à 'spotify_etl', pas 'airflow_db'")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    diagnose()