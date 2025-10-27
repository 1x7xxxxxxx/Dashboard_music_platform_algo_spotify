"""Collecteur pour YouTube Data API v3."""
from googleapiclient.discovery import build
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YouTubeCollector:
    """Collecte les données YouTube Data API v3."""
    
    def __init__(self, api_key: str):
        """
        Initialise le collecteur YouTube.
        
        Args:
            api_key: Clé API YouTube Data API v3
        """
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        logger.info("✅ YouTubeCollector initialisé")
    
    def get_channel_stats(self, channel_id: str) -> Optional[Dict]:
        """
        Récupère les statistiques d'une chaîne.
        
        Args:
            channel_id: ID de la chaîne YouTube
            
        Returns:
            Dict avec les stats de la chaîne
        """
        try:
            request = self.youtube.channels().list(
                part='statistics,snippet,contentDetails',
                id=channel_id
            )
            response = request.execute()
            
            if not response.get('items'):
                logger.error(f"❌ Chaîne {channel_id} introuvable")
                return None
            
            channel = response['items'][0]
            stats = channel['statistics']
            snippet = channel['snippet']
            
            data = {
                'channel_id': channel_id,
                'channel_name': snippet.get('title'),
                'description': snippet.get('description'),
                'published_at': snippet.get('publishedAt'),
                'subscriber_count': int(stats.get('subscriberCount', 0)),
                'video_count': int(stats.get('videoCount', 0)),
                'view_count': int(stats.get('viewCount', 0)),
                'thumbnail_url': snippet.get('thumbnails', {}).get('default', {}).get('url'),
                'country': snippet.get('country'),
                'collected_at': datetime.now()
            }
            
            logger.info(f"✅ Stats chaîne {snippet.get('title')}: {stats.get('subscriberCount')} abonnés")
            return data
            
        except Exception as e:
            logger.error(f"❌ Erreur get_channel_stats: {e}")
            return None
    
    def get_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict]:
        """
        Récupère la liste des vidéos d'une chaîne.
        
        Args:
            channel_id: ID de la chaîne YouTube
            max_results: Nombre max de vidéos à récupérer (max 50 par requête)
            
        Returns:
            Liste de dicts avec les vidéos
        """
        videos = []
        
        try:
            # Récupérer l'ID de la playlist "uploads"
            request = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            )
            response = request.execute()
            
            if not response.get('items'):
                logger.error(f"❌ Chaîne {channel_id} introuvable")
                return videos
            
            uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Récupérer les vidéos de la playlist
            next_page_token = None
            
            while len(videos) < max_results:
                request = self.youtube.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=uploads_playlist_id,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token
                )
                response = request.execute()
                
                for item in response.get('items', []):
                    snippet = item['snippet']
                    video_id = snippet['resourceId']['videoId']
                    
                    video_data = {
                        'video_id': video_id,
                        'channel_id': channel_id,
                        'title': snippet.get('title'),
                        'description': snippet.get('description'),
                        'published_at': snippet.get('publishedAt'),
                        'thumbnail_url': snippet.get('thumbnails', {}).get('default', {}).get('url'),
                        'collected_at': datetime.now()
                    }
                    
                    videos.append(video_data)
                
                next_page_token = response.get('nextPageToken')
                
                if not next_page_token:
                    break
            
            logger.info(f"✅ {len(videos)} vidéos récupérées")
            return videos
            
        except Exception as e:
            logger.error(f"❌ Erreur get_channel_videos: {e}")
            return videos
    
    def get_video_stats(self, video_ids: List[str]) -> List[Dict]:
        """
        Récupère les statistiques de plusieurs vidéos.
        
        Args:
            video_ids: Liste des IDs de vidéos (max 50 par requête)
            
        Returns:
            Liste de dicts avec les stats
        """
        stats_list = []
        
        try:
            # L'API YouTube accepte max 50 IDs par requête
            for i in range(0, len(video_ids), 50):
                batch_ids = video_ids[i:i+50]
                
                request = self.youtube.videos().list(
                    part='statistics,contentDetails,snippet',
                    id=','.join(batch_ids)
                )
                response = request.execute()
                
                for item in response.get('items', []):
                    video_id = item['id']
                    stats = item.get('statistics', {})
                    details = item.get('contentDetails', {})
                    snippet = item.get('snippet', {})
                    
                    data = {
                        'video_id': video_id,
                        'title': snippet.get('title'),
                        'view_count': int(stats.get('viewCount', 0)),
                        'like_count': int(stats.get('likeCount', 0)),
                        'comment_count': int(stats.get('commentCount', 0)),
                        'favorite_count': int(stats.get('favoriteCount', 0)),
                        'duration': details.get('duration'),
                        'definition': details.get('definition'),
                        'collected_at': datetime.now()
                    }
                    
                    stats_list.append(data)
            
            logger.info(f"✅ Stats de {len(stats_list)} vidéos récupérées")
            return stats_list
            
        except Exception as e:
            logger.error(f"❌ Erreur get_video_stats: {e}")
            return stats_list
    
    def get_video_comments(self, video_id: str, max_results: int = 100) -> List[Dict]:
        """
        Récupère les commentaires d'une vidéo.
        
        Args:
            video_id: ID de la vidéo
            max_results: Nombre max de commentaires
            
        Returns:
            Liste de dicts avec les commentaires
        """
        comments = []
        
        try:
            next_page_token = None
            
            while len(comments) < max_results:
                request = self.youtube.commentThreads().list(
                    part='snippet',
                    videoId=video_id,
                    maxResults=min(100, max_results - len(comments)),
                    pageToken=next_page_token,
                    order='relevance'
                )
                response = request.execute()
                
                for item in response.get('items', []):
                    snippet = item['snippet']['topLevelComment']['snippet']
                    
                    comment_data = {
                        'video_id': video_id,
                        'comment_id': item['id'],
                        'author': snippet.get('authorDisplayName'),
                        'text': snippet.get('textDisplay'),
                        'like_count': int(snippet.get('likeCount', 0)),
                        'published_at': snippet.get('publishedAt'),
                        'collected_at': datetime.now()
                    }
                    
                    comments.append(comment_data)
                
                next_page_token = response.get('nextPageToken')
                
                if not next_page_token:
                    break
            
            logger.info(f"✅ {len(comments)} commentaires récupérés pour vidéo {video_id}")
            return comments
            
        except Exception as e:
            logger.error(f"❌ Erreur get_video_comments: {e}")
            return comments
    
    def get_playlists(self, channel_id: str) -> List[Dict]:
        """
        Récupère les playlists d'une chaîne.
        
        Args:
            channel_id: ID de la chaîne
            
        Returns:
            Liste de dicts avec les playlists
        """
        playlists = []
        
        try:
            next_page_token = None
            
            while True:
                request = self.youtube.playlists().list(
                    part='snippet,contentDetails',
                    channelId=channel_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                response = request.execute()
                
                for item in response.get('items', []):
                    snippet = item['snippet']
                    details = item['contentDetails']
                    
                    playlist_data = {
                        'playlist_id': item['id'],
                        'channel_id': channel_id,
                        'title': snippet.get('title'),
                        'description': snippet.get('description'),
                        'video_count': int(details.get('itemCount', 0)),
                        'published_at': snippet.get('publishedAt'),
                        'thumbnail_url': snippet.get('thumbnails', {}).get('default', {}).get('url'),
                        'collected_at': datetime.now()
                    }
                    
                    playlists.append(playlist_data)
                
                next_page_token = response.get('nextPageToken')
                
                if not next_page_token:
                    break
            
            logger.info(f"✅ {len(playlists)} playlists récupérées")
            return playlists
            
        except Exception as e:
            logger.error(f"❌ Erreur get_playlists: {e}")
            return playlists
    
    def collect_all_data(self, channel_id: str, max_videos: int = 50, 
                        collect_comments: bool = False) -> Dict:
        """
        Collecte toutes les données d'une chaîne.
        
        Args:
            channel_id: ID de la chaîne YouTube
            max_videos: Nombre max de vidéos à récupérer
            collect_comments: Si True, récupère les commentaires (coûteux en quota)
            
        Returns:
            Dict avec toutes les données
        """
        logger.info(f"🚀 Début collecte chaîne {channel_id}")
        
        data = {
            'channel_stats': None,
            'videos': [],
            'video_stats': [],
            'playlists': [],
            'comments': []
        }
        
        # Stats de la chaîne
        data['channel_stats'] = self.get_channel_stats(channel_id)
        
        # Liste des vidéos
        data['videos'] = self.get_channel_videos(channel_id, max_videos)
        
        # Stats des vidéos
        if data['videos']:
            video_ids = [v['video_id'] for v in data['videos']]
            data['video_stats'] = self.get_video_stats(video_ids)
        
        # Playlists
        data['playlists'] = self.get_playlists(channel_id)
        
        # Commentaires (optionnel, coûteux en quota)
        if collect_comments and data['videos']:
            # Récupérer commentaires des 5 dernières vidéos seulement
            for video in data['videos'][:5]:
                comments = self.get_video_comments(video['video_id'], max_results=20)
                data['comments'].extend(comments)
        
        logger.info("✅ Collecte terminée")
        return data


# Test
if __name__ == "__main__":
    import os
    
    api_key = os.getenv('YOUTUBE_API_KEY')
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    
    if not api_key or not channel_id:
        print("❌ Variables YOUTUBE_API_KEY et YOUTUBE_CHANNEL_ID requises")
        exit(1)
    
    collector = YouTubeCollector(api_key)
    data = collector.collect_all_data(channel_id, max_videos=10, collect_comments=False)
    
    print("\n📊 Résumé:")
    print(f"   Chaîne: {data['channel_stats']['channel_name']}")
    print(f"   Abonnés: {data['channel_stats']['subscriber_count']:,}")
    print(f"   Vidéos: {len(data['videos'])}")
    print(f"   Playlists: {len(data['playlists'])}")