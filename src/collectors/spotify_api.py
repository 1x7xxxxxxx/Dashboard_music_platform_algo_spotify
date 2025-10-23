"""Collector pour l'API Spotify."""
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import time


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SpotifyCollector:
    """Collecte les données depuis l'API Spotify."""
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Initialise le collector Spotify.
        
        Args:
            client_id: Client ID Spotify
            client_secret: Client Secret Spotify
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.sp = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authentification auprès de l'API Spotify."""
        try:
            auth_manager = SpotifyClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            logger.info("✅ Authentification Spotify réussie")
        except Exception as e:
            logger.error(f"❌ Erreur d'authentification Spotify: {e}")
            raise
    
    def get_artist_info(self, artist_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'un artiste.
        
        Args:
            artist_id: ID Spotify de l'artiste
            
        Returns:
            Dictionnaire avec les infos de l'artiste ou None si erreur
        """
        try:
            artist = self.sp.artist(artist_id)
            
            data = {
                'artist_id': artist['id'],
                'name': artist['name'],
                'followers': artist['followers']['total'],
                'popularity': artist['popularity'],
                'genres': artist['genres'],
                'collected_at': datetime.now()  # ✅ datetime object, pas string
            }
            
            logger.info(f"✅ Données récupérées pour l'artiste: {artist['name']}")
            return data
            
        except spotipy.exceptions.SpotifyException as e:
            logger.error(f"❌ Erreur API Spotify pour artiste {artist_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur inattendue: {e}")
            return None
    
    def get_artist_top_tracks(self, artist_id: str, market: str = 'FR') -> List[Dict[str, Any]]:
        """
        Récupère les top tracks d'un artiste.
        
        Args:
            artist_id: ID Spotify de l'artiste
            market: Code du marché (pays)
            
        Returns:
            Liste des top tracks
        """
        try:
            results = self.sp.artist_top_tracks(artist_id, country=market)
            
            tracks = []
            for track in results['tracks']:
                track_data = {
                    'track_id': track['id'],
                    'track_name': track['name'],
                    'artist_id': artist_id,
                    'popularity': track['popularity'],
                    'duration_ms': track['duration_ms'],
                    'explicit': track['explicit'],
                    'album_name': track['album']['name'],
                    'release_date': track['album']['release_date'],
                    'collected_at': datetime.now()  # ✅ datetime object, pas string
                }
                tracks.append(track_data)
            
            logger.info(f"✅ {len(tracks)} top tracks récupérés pour artiste {artist_id}")
            return tracks
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des top tracks: {e}")
            return []
    
    def get_track_audio_features(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les caractéristiques audio d'un track.
        
        Args:
            track_id: ID Spotify du track
            
        Returns:
            Dictionnaire avec les audio features
        """
        try:
            features = self.sp.audio_features(track_id)[0]
            
            if features:
                data = {
                    'track_id': track_id,
                    'danceability': features['danceability'],
                    'energy': features['energy'],
                    'key': features['key'],
                    'loudness': features['loudness'],
                    'mode': features['mode'],
                    'speechiness': features['speechiness'],
                    'acousticness': features['acousticness'],
                    'instrumentalness': features['instrumentalness'],
                    'liveness': features['liveness'],
                    'valence': features['valence'],
                    'tempo': features['tempo'],
                    'collected_at': datetime.now()  # ✅ datetime object, pas string
                }
                
                logger.info(f"✅ Audio features récupérés pour track {track_id}")
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des audio features: {e}")
            return None
    
    def search_artist(self, artist_name: str) -> Optional[str]:
        """
        Recherche un artiste par nom et retourne son ID.
        
        Args:
            artist_name: Nom de l'artiste
            
        Returns:
            ID Spotify de l'artiste ou None
        """
        try:
            results = self.sp.search(q=f'artist:{artist_name}', type='artist', limit=1)
            
            if results['artists']['items']:
                artist_id = results['artists']['items'][0]['id']
                logger.info(f"✅ Artiste trouvé: {artist_name} (ID: {artist_id})")
                return artist_id
            else:
                logger.warning(f"⚠️ Aucun artiste trouvé pour: {artist_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la recherche d'artiste: {e}")
            return None


# Exemple d'utilisation
if __name__ == "__main__":
    # Import relatif
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    from src.utils.config_loader import config_loader
    
    # Charger la config
    config = config_loader.load()
    spotify_config = config['spotify']
    
    # Créer le collector
    collector = SpotifyCollector(
        client_id=spotify_config['client_id'],
        client_secret=spotify_config['client_secret']
    )
    
    # Exemple: Rechercher et récupérer les infos d'un artiste
    artist_name = "Daft Punk"
    artist_id = collector.search_artist(artist_name)
    
    if artist_id:
        artist_info = collector.get_artist_info(artist_id)
        print(f"\n📊 Infos artiste: {artist_info}")
        
        top_tracks = collector.get_artist_top_tracks(artist_id)
        print(f"\n🎵 Top tracks: {len(top_tracks)} tracks récupérés")