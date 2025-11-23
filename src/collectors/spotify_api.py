"""Collector pour l'API Spotify."""
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

# Configuration du logging
# Note: On laisse Airflow gérer le formatage global, on récupère juste le logger
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
                'collected_at': datetime.now()  # ✅ datetime object pour Postgres
            }
            
            logger.info(f"✅ Données récupérées pour l'artiste: {artist['name']}")
            return data
            
        except Exception as e:
            logger.error(f"❌ Erreur API Spotify pour artiste {artist_id}: {e}")
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
                # Gestion sécurisée de la date de sortie (parfois YYYY seulement)
                release_date = track['album']['release_date']
                
                track_data = {
                    'track_id': track['id'],
                    'track_name': track['name'],
                    'artist_id': artist_id,
                    'popularity': track['popularity'],
                    'duration_ms': track['duration_ms'],
                    'explicit': track['explicit'],
                    'album_name': track['album']['name'],
                    'release_date': release_date,
                    'collected_at': datetime.now()
                }
                tracks.append(track_data)
            
            logger.info(f"✅ {len(tracks)} top tracks récupérés pour artiste {artist_id}")
            return tracks
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des top tracks: {e}")
            return []
    
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