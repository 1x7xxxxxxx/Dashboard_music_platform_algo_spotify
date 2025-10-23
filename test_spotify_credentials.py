"""Test des credentials Spotify."""
import os
from dotenv import load_dotenv

# Charger .env
load_dotenv()

print("\n" + "="*70)
print("🔍 TEST CREDENTIALS SPOTIFY")
print("="*70 + "\n")

client_id = os.getenv('SPOTIFY_CLIENT_ID')
client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
artist_ids = os.getenv('SPOTIFY_ARTIST_IDS')

print(f"📋 CLIENT_ID: {client_id[:20]}... (trouvé)" if client_id else "❌ CLIENT_ID: Non trouvé")
print(f"📋 CLIENT_SECRET: {client_secret[:20]}... (trouvé)" if client_secret else "❌ CLIENT_SECRET: Non trouvé")
print(f"📋 ARTIST_IDS: {artist_ids}" if artist_ids else "❌ ARTIST_IDS: Non trouvé")

if not client_id or not client_secret:
    print("\n❌ Credentials manquants ! Configurez votre .env")
    exit(1)

print("\n🧪 Test de connexion à l'API Spotify...")

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    
    auth_manager = SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    # Test avec un artiste connu (Daft Punk)
    test_artist = sp.artist('4tZwfgrHOc3mvqYlEYSvVi')
    print(f"✅ Connexion réussie !")
    print(f"✅ Test artiste : {test_artist['name']}")
    print(f"✅ Followers : {test_artist['followers']['total']:,}")
    print(f"✅ Popularité : {test_artist['popularity']}/100")
    
    # Test avec vos artistes
    if artist_ids:
        print(f"\n🎸 Test de vos artistes configurés...")
        for artist_id in artist_ids.split(','):
            artist_id = artist_id.strip()
            if artist_id:
                try:
                    artist = sp.artist(artist_id)
                    print(f"   ✅ {artist['name']} (ID: {artist_id})")
                except Exception as e:
                    print(f"   ❌ Erreur pour {artist_id}: {e}")
    
    print("\n" + "="*70)
    print("✅ TOUS LES TESTS PASSÉS")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"\n❌ ERREUR: {e}")
    print("\n💡 Vérifiez que vos credentials Spotify sont corrects")
    print("   https://developer.spotify.com/dashboard/applications")
    exit(1)