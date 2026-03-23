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
from src.utils.retry import retry

# Chargement .env
load_dotenv()

class SoundCloudCollector:
    def __init__(self):
        self.client_id = os.getenv("SOUNDCLOUD_CLIENT_ID")
        self.user_id = os.getenv("SOUNDCLOUD_USER_ID")
        
        # Récupération dynamique des infos BDD
        # Si vous testez en local hors docker, assurez-vous que localhost pointe bien sur le bon port
        self.db_host = os.getenv('DATABASE_HOST', 'localhost')
        self.db_port = os.getenv('DATABASE_PORT', '5432') # <-- On remet 5432 par défaut
        self.db_name = os.getenv('DATABASE_NAME')
        self.db_user = os.getenv('DATABASE_USER')
        self.db_pass = os.getenv('DATABASE_PASSWORD')

        if not self.client_id or not self.user_id:
            raise ValueError("❌ Manque SOUNDCLOUD_CLIENT_ID ou SOUNDCLOUD_USER_ID dans .env")
            
        self.base_url = "https://api-v2.soundcloud.com"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Origin': 'https://soundcloud.com',
            'Referer': 'https://soundcloud.com/'
        }
        
        print(f"🔌 Tentative de connexion BDD vers {self.db_host}:{self.db_port}...")
        try:
            self.db = PostgresHandler(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_pass
            )
            print("✅ Connexion BDD réussie (Objet créé).")
        except Exception as e:
            print(f"❌ CRASH Connexion BDD : {e}")
            self.db = None

    @retry(max_attempts=3, backoff="exponential")
    def fetch_tracks(self):
        print(f"🎵 Récupération SoundCloud pour User {self.user_id}...")
        tracks_data = []
        limit = 50
        offset = 0
        
        while True:
            url = f"{self.base_url}/users/{self.user_id}/tracks"
            params = {
                'client_id': self.client_id,
                'limit': limit,
                'offset': offset,
                'linked_partitioning': 1,
                'app_locale': 'en'
            }
            
            try:
                response = requests.get(url, params=params, headers=self.headers)
                
                if response.status_code != 200:
                    print(f"❌ Erreur API {response.status_code}")
                    break
                
                data = response.json()
                
                if 'collection' in data:
                    for track in data['collection']:
                        # On prépare l'objet propre pour la BDD
                        tracks_data.append({
                            'track_id': str(track.get('id')), # Conversion string au cas où
                            'title': track.get('title'),
                            'permalink_url': track.get('permalink_url'),
                            'playback_count': int(track.get('playback_count', 0)),
                            'likes_count': int(track.get('likes_count', 0)),
                            'reposts_count': int(track.get('reposts_count', 0)),
                            'comment_count': int(track.get('comment_count', 0)),
                            'collected_at': datetime.now().strftime('%Y-%m-%d')
                        })
                
                if data.get('next_href'):
                    offset += limit
                else:
                    break
                    
            except Exception as e:
                print(f"❌ Erreur Fetch: {e}")
                break
        
        print(f"✅ {len(tracks_data)} titres trouvés via l'API.")
        return tracks_data

    def save_to_db(self, tracks):
        if not tracks:
            print("⚠️ Liste vide, rien à sauvegarder.")
            return

        if not self.db:
            print("❌ Pas de connexion BDD active. Abandon.")
            return

        print(f"💾 Tentative d'insertion de {len(tracks)} lignes...")
        
        # 1. Suppression des données du jour pour éviter les doublons
        delete_query = "DELETE FROM soundcloud_tracks_daily WHERE collected_at = CURRENT_DATE"
        
        try:
            # On tente d'abord la suppression
            with self.db.conn.cursor() as cur:
                cur.execute(delete_query)
                self.db.conn.commit()
            print("   🧹 Nettoyage des données du jour effectué.")
            
            # 2. Insertion
            # Vérification que la méthode insert_many existe bien dans votre PostgresHandler
            # Sinon on fait une boucle simple pour tester
            try:
                self.db.insert_many("soundcloud_tracks_daily", tracks)
                print("   ✅ INSERT SUCCESS ! Données sauvegardées.")
            except AttributeError:
                print("   ⚠️ Méthode insert_many introuvable, tentative manuelle...")
                # Fallback manuel si insert_many n'est pas défini
                query = """
                    INSERT INTO soundcloud_tracks_daily 
                    (track_id, title, permalink_url, playback_count, likes_count, reposts_count, comment_count, collected_at)
                    VALUES (%(track_id)s, %(title)s, %(permalink_url)s, %(playback_count)s, %(likes_count)s, %(reposts_count)s, %(comment_count)s, %(collected_at)s)
                """
                with self.db.conn.cursor() as cur:
                    for t in tracks:
                        cur.execute(query, t)
                    self.db.conn.commit()
                print("   ✅ INSERT MANUEL SUCCESS !")

        except Exception as e:
            print(f"❌ ERREUR SQL CRITIQUE : {e}")
            # Si l'erreur mentionne que la table n'existe pas, c'est le moment de la créer !
            if "relation" in str(e) and "does not exist" in str(e):
                print("💡 CONSEIL : Vérifiez que la table 'soundcloud_tracks_daily' existe bien dans PgAdmin.")

    def run(self):
        tracks = self.fetch_tracks()
        self.save_to_db(tracks)
        if self.db:
            self.db.close()

if __name__ == "__main__":
    collector = SoundCloudCollector()
    collector.run()