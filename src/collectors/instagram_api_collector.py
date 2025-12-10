import os
import sys
import requests
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Chemin racine
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler

load_dotenv()

class InstagramCollector:
    def __init__(self):
        # On a besoin d'un Token Meta (Long-Lived idéalement)
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        # L'ID du compte Instagram Business (pas le nom d'utilisateur)
        self.ig_user_id = os.getenv("INSTAGRAM_USER_ID")
        
        if not self.access_token or not self.ig_user_id:
            raise ValueError("❌ Manque INSTAGRAM_ACCESS_TOKEN ou INSTAGRAM_USER_ID dans .env")
            
        self.base_url = "https://graph.facebook.com/v18.0"
        
        # Connexion BDD (Port 5433 pour Docker externe)
        print("🔌 Connexion BDD via le port 5433 (Docker Externe)...")
        self.db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=5433,
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )

    def fetch_stats(self):
        """Récupère les stats du compte."""
        print(f"📸 Connexion à Instagram Graph API ({self.ig_user_id})...")
        
        # Endpoint: /{ig-user-id}?fields=...
        url = f"{self.base_url}/{self.ig_user_id}"
        params = {
            'fields': 'username,followers_count,follows_count,media_count',
            'access_token': self.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            stats = {
                'ig_user_id': data.get('id'),
                'username': data.get('username'),
                'followers_count': data.get('followers_count', 0),
                'follows_count': data.get('follows_count', 0),
                'media_count': data.get('media_count', 0),
                'collected_at': datetime.now().strftime('%Y-%m-%d')
            }
            
            print(f"✅ Données récupérées pour @{stats['username']} : {stats['followers_count']} abonnés.")
            return stats
            
        except Exception as e:
            print(f"❌ Erreur API: {e}")
            if response.status_code == 400:
                print("⚠️ Vérifiez que le Token est valide et que l'ID est bien un 'Instagram Business ID'.")
            return None

    def save_to_db(self, stats):
        if not stats: return

        print("💾 Sauvegarde en base de données...")
        
        # Nettoyage du jour même pour éviter doublons
        delete_query = "DELETE FROM instagram_daily_stats WHERE collected_at = CURRENT_DATE"
        
        insert_query = """
            INSERT INTO instagram_daily_stats 
            (ig_user_id, username, followers_count, follows_count, media_count, collected_at)
            VALUES (%(ig_user_id)s, %(username)s, %(followers_count)s, %(follows_count)s, %(media_count)s, %(collected_at)s)
        """
        
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(delete_query)
                cur.execute(insert_query, stats)
                self.db.conn.commit()
            print("   ✅ Succès.")
            
        except Exception as e:
            print(f"❌ Erreur BDD: {e}")
        finally:
            self.db.close()

    def run(self):
        stats = self.fetch_stats()
        self.save_to_db(stats)     

if __name__ == "__main__":
    InstagramCollector().run()