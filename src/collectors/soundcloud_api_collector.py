import os
import sys
import requests
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Ajout du chemin racine pour les imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler

# Chargement .env
load_dotenv()

class SoundCloudCollector:
    def __init__(self):
        self.client_id = os.getenv("SOUNDCLOUD_CLIENT_ID")
        self.user_id = os.getenv("SOUNDCLOUD_USER_ID")
        
        if not self.client_id or not self.user_id:
            raise ValueError("❌ Manque SOUNDCLOUD_CLIENT_ID ou SOUNDCLOUD_USER_ID dans .env")
            
        self.base_url = "https://api-v2.soundcloud.com"
        
        # ✅ DÉGUISEMENT NAVIGATEUR (User-Agent)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://soundcloud.com/',
            'Origin': 'https://soundcloud.com'
        }
        
        # Connexion BDD (Port forcé 5433 pour Docker local)
        print("🔌 Connexion BDD via le port 5433 (Docker Externe)...")
        self.db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=5433,
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )

    def fetch_tracks(self):
        """Récupère tous les titres de l'artiste."""
        print(f"🎵 Connexion à SoundCloud pour l'utilisateur {self.user_id}...")
        
        tracks_data = []
        limit = 50
        offset = 0
        
        while True:
            # Endpoint V2 pour les tracks d'un user
            url = f"{self.base_url}/users/{self.user_id}/tracks"
            params = {
                'client_id': self.client_id,
                'limit': limit,
                'offset': offset,
                'linked_partitioning': 1,
                'app_locale': 'en' # Ajout pour faire plus "vrai"
            }
            
            try:
                # ✅ AJOUT DES HEADERS ICI
                response = requests.get(url, params=params, headers=self.headers)
                
                if response.status_code == 401:
                    print("❌ Erreur 401 : Client ID invalide (non autorisé).")
                    break
                if response.status_code == 403:
                    print("❌ Erreur 403 : Accès interdit (WAF). Le script est détecté comme un bot.")
                    break
                
                response.raise_for_status()
                data = response.json()
                
                if 'collection' in data:
                    for track in data['collection']:
                        tracks_data.append({
                            'track_id': track.get('id'),
                            'title': track.get('title'),
                            'permalink_url': track.get('permalink_url'),
                            'playback_count': track.get('playback_count', 0),
                            'likes_count': track.get('likes_count', 0),
                            'reposts_count': track.get('reposts_count', 0),
                            'comment_count': track.get('comment_count', 0),
                            'collected_at': datetime.now().strftime('%Y-%m-%d')
                        })
                
                # Gestion de la pagination
                if data.get('next_href'):
                    offset += limit
                else:
                    break
                    
            except Exception as e:
                print(f"❌ Erreur API: {e}")
                break
        
        print(f"✅ {len(tracks_data)} titres récupérés.")
        return tracks_data

    def save_to_db(self, tracks):
        """Sauvegarde les snapshots dans PostgreSQL."""
        if not tracks:
            print("⚠️ Aucune donnée à sauvegarder.")
            return

        print(f"💾 Sauvegarde de {len(tracks)} titres en base de données...")
        
        query = """
            INSERT INTO soundcloud_tracks_daily 
            (track_id, title, permalink_url, playback_count, likes_count, reposts_count, comment_count, collected_at)
            VALUES (%(track_id)s, %(title)s, %(permalink_url)s, %(playback_count)s, %(likes_count)s, %(reposts_count)s, %(comment_count)s, %(collected_at)s)
        """
        
        delete_query = "DELETE FROM soundcloud_tracks_daily WHERE collected_at = CURRENT_DATE"
        
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(delete_query)
                self.db.conn.commit()
            
            self.db.insert_many("soundcloud_tracks_daily", tracks)
            print("   ✅ Données insérées avec succès.")
            
        except Exception as e:
            print(f"❌ Erreur BDD: {e}")
        finally:
            self.db.close()

    def run(self):
        tracks = self.fetch_tracks()
        self.save_to_db(tracks)

if __name__ == "__main__":
    collector = SoundCloudCollector()
    collector.run()