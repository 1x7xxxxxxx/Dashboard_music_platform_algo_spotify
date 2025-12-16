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
        
        # Récupération dynamique des infos BDD
        # Par défaut 5432 (interne docker), mais surchargeable via .env
        self.db_host = os.getenv('DATABASE_HOST', 'localhost')
        self.db_port = os.getenv('DATABASE_PORT', '5432') 
        self.db_name = os.getenv('DATABASE_NAME')
        self.db_user = os.getenv('DATABASE_USER')
        self.db_pass = os.getenv('DATABASE_PASSWORD')

        if not self.access_token or not self.ig_user_id:
            raise ValueError("❌ Manque INSTAGRAM_ACCESS_TOKEN ou INSTAGRAM_USER_ID dans .env")
            
        self.base_url = "https://graph.facebook.com/v18.0"
        
        # Connexion BDD
        print(f"🔌 Tentative connexion BDD vers {self.db_host}:{self.db_port}...")
        try:
            self.db = PostgresHandler(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_pass
            )
            print("✅ Connexion BDD réussie.")
        except Exception as e:
            print(f"❌ Erreur Connexion BDD: {e}")
            self.db = None

    def fetch_stats(self):
        """Récupère les stats du compte."""
        print(f"📸 Appel API Meta pour l'ID {self.ig_user_id}...")
        
        url = f"{self.base_url}/{self.ig_user_id}"
        params = {
            'fields': 'username,followers_count,follows_count,media_count',
            'access_token': self.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            
            # Gestion précise des erreurs Token
            if response.status_code == 401: # Unauthorized
                err = response.json()
                print(f"❌ ERREUR TOKEN 401 : {err.get('error', {}).get('message')}")
                print("💡 SOLUTION : Votre token a expiré. Générez-en un nouveau sur 'Meta Graph API Explorer'.")
                return None
            
            if response.status_code == 400:
                print(f"❌ ERREUR 400 : Vérifiez que l'ID {self.ig_user_id} est bien un ID Business.")
                return None

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
            print(f"❌ Erreur API Générale: {e}")
            return None

    def save_to_db(self, stats):
        if not stats: 
            print("⚠️ Pas de données à sauvegarder.")
            return
        
        if not self.db:
            print("❌ Pas de connexion BDD active.")
            return

        print("💾 Sauvegarde en base de données...")
        
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
            print("   ✅ Succès : Stats Instagram insérées.")
            
        except Exception as e:
            print(f"❌ Erreur SQL: {e}")
            if "relation" in str(e) and "does not exist" in str(e):
                print("💡 TABLE MANQUANTE. Veuillez exécuter le script SQL de création.")

    def run(self):
        stats = self.fetch_stats()
        self.save_to_db(stats)     
        if self.db:
            self.db.close()

if __name__ == "__main__":
    InstagramCollector().run()