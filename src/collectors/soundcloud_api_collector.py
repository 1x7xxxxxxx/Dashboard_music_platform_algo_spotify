import os
import sys
import re
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ajout du chemin racine pour les imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler
from src.utils.retry import retry

# Chargement .env
load_dotenv()

class SoundCloudCollector:
    def __init__(self, artist_id: int = 1):
        self.artist_id = artist_id
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
        self._client_id_refreshed = False  # guard: at most one auto-refresh per run

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

    @staticmethod
    def _fetch_client_id_from_bundle() -> str:
        """Extract client_id from SoundCloud's public JS bundle.

        SoundCloud embeds the client_id in its main JavaScript bundle.
        Bundles are fetched in parallel (ThreadPoolExecutor) to minimise latency.
        Raises RuntimeError if extraction fails (network issue or regex mismatch).
        """
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })

        html = session.get("https://soundcloud.com", timeout=15).text
        js_urls = list(dict.fromkeys(  # deduplicate while preserving order
            re.findall(r'https://a-v2\.sndcdn\.com/assets/[^"\']+\.js', html)
        ))
        if not js_urls:
            raise RuntimeError("SoundCloud client_id auto-refresh: no JS bundle URLs found in homepage HTML.")

        # Patterns ordered by specificity.
        # SoundCloud client_id is always exactly 32 alphanumeric chars.
        # The value lives in a webpack config module, not necessarily near the
        # n(6).get("client_id") call — search all bundles without prefix constraint.
        _PATTERNS = [
            re.compile(r'client_id\s*:\s*"([a-zA-Z0-9]{32})"'),   # webpack module def (primary)
            re.compile(r'"client_id"\s*:\s*"([a-zA-Z0-9]{32})"'), # JSON string key
            re.compile(r'client_id=([a-zA-Z0-9]{32})(?:[&"\s]|$)'), # query-string in bundle
            re.compile(r'client_id%3D([a-zA-Z0-9]{32})'),           # URL-encoded
        ]

        # Also search the HTML page itself (sometimes client_id appears in inline JSON)
        for pattern in _PATTERNS:
            m = pattern.search(html)
            if m:
                return m.group(1)

        def _search_bundle(url: str):
            try:
                js = session.get(url, timeout=15).text
                for pattern in _PATTERNS:
                    m = pattern.search(js)
                    if m:
                        return m.group(1)
                return None
            except requests.RequestException:
                return None

        # Search all bundles (not just first 5) — client_id module may be in any of them
        with ThreadPoolExecutor(max_workers=min(4, len(js_urls))) as pool:
            futures = {pool.submit(_search_bundle, url): url for url in js_urls}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    for f in futures:
                        f.cancel()
                    return result

        raise RuntimeError(
            "SoundCloud client_id auto-refresh: pattern not found in any JS bundle. "
            "SoundCloud may have changed their bundle structure."
        )

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
                
                if response.status_code == 401:
                    if not self._client_id_refreshed:
                        logger.warning("SoundCloud 401 — client_id expired. Starting auto-refresh from JS bundle...")
                        new_id = self._fetch_client_id_from_bundle()
                        self.client_id = new_id
                        os.environ['SOUNDCLOUD_CLIENT_ID'] = new_id
                        self._client_id_refreshed = True
                        logger.info(f"New client_id extracted: {new_id[:8]}… Retrying request.")
                        try:
                            from src.utils.credential_loader import save_platform_credentials
                            save_platform_credentials(self.artist_id, 'soundcloud', {'client_id': new_id})
                            logger.info("client_id persisted to DB (artist_credentials).")
                        except Exception as persist_err:
                            logger.warning(f"client_id persist to DB failed (non-blocking): {persist_err}")
                        continue  # rebuild params with new client_id and retry immediately
                    raise ValueError("SoundCloud API 401 — client_id still invalid after auto-refresh.")
                if response.status_code == 403:
                    raise ValueError(f"SoundCloud API 403 — client_id refusé ou IP bloquée temporairement. Renouveler le client_id via DevTools.")
                if response.status_code != 200:
                    raise ValueError(f"SoundCloud API {response.status_code}: {response.text[:200]}")
                
                data = response.json()
                
                if 'collection' in data:
                    for track in data['collection']:
                        # On prépare l'objet propre pour la BDD
                        tracks_data.append({
                            'artist_id': self.artist_id,
                            'track_id': str(track.get('id')),
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
                    
            except ValueError:
                raise
            except Exception as e:
                raise RuntimeError(f"SoundCloud fetch error: {e}") from e
        
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
        
        delete_query = "DELETE FROM soundcloud_tracks_daily WHERE collected_at = CURRENT_DATE AND artist_id = %s"

        try:
            self.db.execute_query(delete_query, (self.artist_id,))
            print("   🧹 Nettoyage des données du jour effectué.")

            # 2. Insertion
            self.db.insert_many("soundcloud_tracks_daily", tracks)
            print("   ✅ INSERT SUCCESS ! Données sauvegardées.")

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