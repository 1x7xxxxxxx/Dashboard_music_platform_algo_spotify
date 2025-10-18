"""Script pour collecter les données Spotify et les stocker dans PostgreSQL."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.utils.config_loader import config_loader
from src.collectors.spotify_api import SpotifyCollector
from src.database.postgresql_handler import PostgreSQLHandler

print("🚀 Démarrage de la collecte ETL Spotify\n")

# 1. Charger la configuration
config = config_loader.load()
spotify_config = config['spotify']
db_config = config['database']

# 2. Initialiser les composants
print("🔌 Connexion aux services...")
collector = SpotifyCollector(
    client_id=spotify_config['client_id'],
    client_secret=spotify_config['client_secret']
)

db = PostgreSQLHandler(
    host=db_config['host'],
    port=db_config['port'],
    database=db_config['database'],
    user=db_config['user'],
    password=db_config['password']
)

# 3. Récupérer les artistes actifs
active_artists = config_loader.get_active_artists()
print(f"\n📋 {len(active_artists)} artiste(s) à traiter\n")

# 4. Collecter et stocker les données
for artist_config in active_artists:
    artist_name = artist_config['name']
    artist_id = artist_config.get('spotify_id')
    
    print(f"{'='*60}")
    print(f"🎵 Traitement: {artist_name}")
    print(f"{'='*60}")
    
    # Si pas d'ID, chercher par nom
    if not artist_id:
        artist_id = collector.search_artist(artist_name)
        if not artist_id:
            print(f"❌ Artiste non trouvé: {artist_name}\n")
            continue
    
    # Collecter les infos de l'artiste
    artist_info = collector.get_artist_info(artist_id)
    if not artist_info:
        print(f"❌ Impossible de récupérer les infos\n")
        continue
    
    print(f"\n📊 Informations artiste:")
    print(f"   👤 Nom: {artist_info['name']}")
    print(f"   👥 Followers: {artist_info['followers']:,}")
    print(f"   🔥 Popularité: {artist_info['popularity']}/100")
    print(f"   🎸 Genres: {', '.join(artist_info['genres']) if artist_info['genres'] else 'Aucun'}")
    
    # Stocker dans la base
    print(f"\n💾 Stockage en base de données...")
    db.insert_artist(artist_info)
    db.insert_artist_history(artist_info)
    
    # Collecter les top tracks
    top_tracks = collector.get_artist_top_tracks(artist_id)
    if top_tracks:
        print(f"\n🎵 Top Tracks ({len(top_tracks)}):")
        for i, track in enumerate(top_tracks[:5], 1):
            print(f"   {i}. {track['track_name']} - Popularité: {track['popularity']}/100")
        
        # Stocker les tracks
        db.insert_tracks(top_tracks)
        print(f"\n💾 {len(top_tracks)} tracks stockés")
    
    print(f"\n✅ Traitement terminé pour {artist_name}\n")

print("="*60)
print("🎉 COLLECTE ETL TERMINÉE AVEC SUCCÈS !")
print("="*60)
print("\n💡 Prochaines étapes:")
print("   1. Vérifier les données dans pgAdmin")
print("   2. Créer le dashboard Streamlit pour visualiser")
print("   3. Configurer Airflow pour automatiser quotidiennement")