import os
import sys
import requests
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Chemin racine
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler
from src.utils.retry import retry

load_dotenv()

class InstagramCollector:
    def __init__(self, artist_id: int = 1):
        self.artist_id = artist_id
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

        self.app_id = os.getenv("META_APP_ID")
        self.app_secret = os.getenv("META_APP_SECRET")
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

    def _refresh_access_token(self) -> bool:
        """Exchange current long-lived token for a new one via Meta's token endpoint.

        Requires app_id and app_secret (loaded from env or DB credentials).
        On success: updates self.access_token, persists to DB with new expires_at.
        Returns True on success, False on failure (non-blocking — collect continues
        with the current token so existing valid tokens are not interrupted).
        """
        if not self.app_id or not self.app_secret:
            logger.warning("Meta token refresh skipped: app_id or app_secret not available.")
            return False

        try:
            r = requests.get(
                f"{self.base_url}/oauth/access_token",
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': self.app_id,
                    'client_secret': self.app_secret,
                    'fb_exchange_token': self.access_token,
                },
                timeout=10,
            )
            data = r.json()
            if r.status_code != 200 or 'access_token' not in data:
                logger.warning(f"Meta token refresh failed: {data.get('error', data)}")
                return False

            new_token = data['access_token']
            # Meta returns expires_in in seconds for long-lived tokens (~5184000s = 60 days)
            expires_in = data.get('expires_in', 5184000)
            new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            self.access_token = new_token
            os.environ['INSTAGRAM_ACCESS_TOKEN'] = new_token

            try:
                from src.utils.credential_loader import update_platform_secret
                update_platform_secret(
                    self.artist_id, 'meta', 'access_token', new_token,
                    expires_at=new_expires_at,
                )
                logger.info(f"Meta access_token refreshed and persisted. New expires_at: {new_expires_at.date()}")
            except Exception as e:
                logger.warning(f"Token persist to DB failed (non-blocking): {e}")

            return True

        except Exception as e:
            logger.warning(f"Meta token refresh exception: {e}")
            return False

    def _check_proactive_refresh(self) -> None:
        """Refresh the token proactively if it expires within 15 days.

        Reads expires_at from DB. If within threshold, calls _refresh_access_token().
        Silently skips if expires_at is not set or DB is unavailable.
        """
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.db_host, port=self.db_port, database=self.db_name,
                user=self.db_user, password=self.db_pass
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT expires_at FROM artist_credentials WHERE artist_id = %s AND platform = 'meta'",
                (self.artist_id,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            if not row or not row[0]:
                return

            expires_at = row[0]
            days_left = (expires_at - datetime.utcnow()).days
            if days_left <= 15:
                logger.info(f"Meta token expires in {days_left} day(s) — triggering proactive refresh.")
                self._refresh_access_token()
        except Exception as e:
            logger.debug(f"Proactive refresh check skipped: {e}")

    @retry(max_attempts=3, backoff="exponential")
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
            if response.status_code == 401:
                err = response.json()
                msg = err.get('error', {}).get('message', 'unknown')
                raise ValueError(
                    f"Instagram API 401 — token expired or invalid: {msg}. "
                    "Action: Dashboard → Credentials → Meta → generate a new long-lived token."
                )

            if response.status_code == 400:
                err_body = {}
                try:
                    err_body = response.json().get('error', {})
                except Exception:
                    pass
                err_code = err_body.get('code', '')
                err_msg = err_body.get('message', '')
                # code 190 = token expired/invalid; code 100 = wrong user_id
                if err_code == 190 or 'token' in err_msg.lower():
                    raise ValueError(
                        f"Instagram API 400 (code {err_code}) — access_token expired or invalid: {err_msg}. "
                        "Action: Dashboard → Credentials → Meta → generate a new long-lived token (60 days)."
                    )
                raise ValueError(
                    f"Instagram API 400 (code {err_code}) — ig_user_id={self.ig_user_id} may not be a "
                    f"Business/Creator account ID, or token lacks instagram_basic permission: {err_msg}. "
                    "Action: Dashboard → Credentials → Meta → verify ig_user_id and token permissions."
                )

            response.raise_for_status()
            data = response.json()

            stats = {
                'artist_id': self.artist_id,
                'ig_user_id': data.get('id'),
                'username': data.get('username'),
                'followers_count': data.get('followers_count', 0),
                'follows_count': data.get('follows_count', 0),
                'media_count': data.get('media_count', 0),
                'collected_at': datetime.now().strftime('%Y-%m-%d')
            }

            print(f"✅ Données récupérées pour @{stats['username']} : {stats['followers_count']} abonnés.")
            return stats

        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Instagram API request failed: {e}") from e

    def save_to_db(self, stats):
        if not stats: 
            print("⚠️ Pas de données à sauvegarder.")
            return
        
        if not self.db:
            print("❌ Pas de connexion BDD active.")
            return

        print("💾 Sauvegarde en base de données...")
        
        delete_query = "DELETE FROM instagram_daily_stats WHERE collected_at = CURRENT_DATE AND artist_id = %s"

        insert_query = """
            INSERT INTO instagram_daily_stats
            (artist_id, ig_user_id, username, followers_count, follows_count, media_count, collected_at)
            VALUES (%(artist_id)s, %(ig_user_id)s, %(username)s, %(followers_count)s, %(follows_count)s, %(media_count)s, %(collected_at)s)
            ON CONFLICT (artist_id, ig_user_id, collected_at) DO UPDATE SET
                username = EXCLUDED.username,
                followers_count = EXCLUDED.followers_count,
                follows_count = EXCLUDED.follows_count,
                media_count = EXCLUDED.media_count
        """
        
        try:
            self.db.execute_query(delete_query, (self.artist_id,))
            self.db.execute_query(insert_query, stats)
            print("   ✅ Succès : Stats Instagram insérées.")

        except Exception as e:
            print(f"❌ Erreur SQL: {e}")
            if "relation" in str(e) and "does not exist" in str(e):
                print("💡 TABLE MANQUANTE. Veuillez exécuter le script SQL de création.")

    def run(self):
        self._check_proactive_refresh()
        stats = self.fetch_stats()
        self.save_to_db(stats)
        if self.db:
            self.db.close()

if __name__ == "__main__":
    InstagramCollector().run()