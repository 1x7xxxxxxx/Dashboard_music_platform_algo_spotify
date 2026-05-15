import os
import sys
import requests
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Chemin racine
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler
from src.utils.retry import retry
from src.utils.meta_config import META_GRAPH_BASE_URL

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
        self.base_url = META_GRAPH_BASE_URL
        self.session = requests.Session()
        
        # Connexion BDD
        self.db = PostgresHandler(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=self.db_pass
        )

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
            r = self.session.get(
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
            # Do NOT write to os.environ — would expose the token to child processes
            # and /proc/<pid>/environ. Persist via DB only.

            try:
                from src.utils.credential_loader import update_platform_secret
                update_platform_secret(
                    self.artist_id, 'meta', 'access_token', new_token,
                    expires_at=new_expires_at,
                )
                logger.info(f"Meta access_token refreshed and persisted. New expires_at: {new_expires_at.date()}")
            except Exception as e:
                logger.error(f"Token persist to DB failed: {e}")
                raise

            return True

        except Exception as e:
            logger.warning(f"Meta token refresh exception: {e}")
            return False

    def _check_proactive_refresh(self) -> None:
        """Refresh the token proactively if it expires within 15 days.

        Reuses self.db (already open) — avoids opening a second DB connection.
        Silently skips if expires_at is not set or DB is unavailable.
        """
        if not self.db:
            return
        try:
            rows = self.db.fetch_query(
                "SELECT expires_at FROM artist_credentials WHERE artist_id = %s AND platform = 'meta'",
                (self.artist_id,)
            )
            if not rows or not rows[0][0]:
                return

            expires_at = rows[0][0]
            if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            days_left = (expires_at - datetime.utcnow()).days
            if days_left <= 15:
                logger.info(f"Meta token expires in {days_left} day(s) — triggering proactive refresh.")
                self._refresh_access_token()
        except Exception as e:
            logger.debug(f"Proactive refresh check skipped: {e}")

    @retry(max_attempts=3, backoff="exponential")
    def fetch_stats(self):
        """Récupère les stats du compte."""
        logger.info(f"Calling Meta API for IG user {self.ig_user_id}")
        
        url = f"{self.base_url}/{self.ig_user_id}"
        params = {
            'fields': 'username,followers_count,follows_count,media_count',
            'access_token': self.access_token
        }
        
        try:
            response = self.session.get(url, params=params)
            
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
                'collected_at': datetime.now(timezone.utc)
            }

            logger.info(f"Fetched stats for @{stats['username']}: {stats['followers_count']} followers")
            return stats

        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Instagram API request failed: {e}") from e

    def save_to_db(self, stats):
        if not stats: 
            logger.warning("No data to save")
            return
        
        if not self.db:
            logger.error("No active DB connection")
            return

        logger.info("Saving Instagram stats to database")
        
        delete_query = "DELETE FROM instagram_daily_stats WHERE collected_at::date = CURRENT_DATE AND artist_id = %s"

        insert_query = """
            INSERT INTO instagram_daily_stats
            (artist_id, ig_user_id, username, followers_count, follows_count, media_count, collected_at)
            VALUES (%(artist_id)s, %(ig_user_id)s, %(username)s, %(followers_count)s, %(follows_count)s, %(media_count)s, %(collected_at)s)
        """
        
        try:
            self.db.execute_query(delete_query, (self.artist_id,))
            self.db.execute_query(insert_query, stats)
            logger.info("Instagram stats inserted")

        except Exception as e:
            logger.error(f"SQL error in save_to_db: {e}")
            if "relation" in str(e) and "does not exist" in str(e):
                logger.error("Missing table — run the schema migration first")
            raise

    def _map_media(self, m: dict) -> dict:
        return {
            'artist_id': self.artist_id,
            'media_id': m.get('id'),
            'caption': m.get('caption'),
            'media_type': m.get('media_type'),
            'permalink': m.get('permalink'),
            'media_url': m.get('media_url'),
            'timestamp': m.get('timestamp'),
            'like_count': m.get('like_count', 0) or 0,
            'comments_count': m.get('comments_count', 0) or 0,
            'collected_at': datetime.now(timezone.utc),
        }

    @retry(max_attempts=3, backoff="exponential")
    def fetch_media(self, max_pages: int = 10) -> list:
        """Fetch the account's posts via /{ig-user-id}/media (paginated, capped)."""
        url = f"{self.base_url}/{self.ig_user_id}/media"
        params = {
            'fields': 'id,caption,media_type,permalink,media_url,'
                      'timestamp,like_count,comments_count',
            'access_token': self.access_token, 'limit': 50,
        }
        media, pages = [], 0
        try:
            while url and pages < max_pages:
                resp = self.session.get(url, params=params if pages == 0 else None)
                if resp.status_code == 401:
                    raise ValueError(
                        "Instagram API 401 — token expired/invalid. Action: "
                        "Dashboard → Credentials → Meta → new long-lived token."
                    )
                if resp.status_code != 200:
                    err = (resp.json().get('error', {})
                           if resp.content else {})
                    raise ValueError(
                        f"Instagram media API {resp.status_code} "
                        f"(code {err.get('code', '')}): {err.get('message', '')[:200]}"
                    )
                data = resp.json()
                media.extend(self._map_media(m) for m in data.get('data', []))
                url = data.get('paging', {}).get('next')
                pages += 1
            if pages >= max_pages and url:
                logger.warning(f"IG media pagination cap ({max_pages}) hit — older posts skipped.")
            logger.info(f"Fetched {len(media)} Instagram media item(s)")
            return media
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Instagram media fetch failed: {e}") from e

    def _media_insight_row(self, mid: str, metrics: str, day) -> dict | None:
        """One media's insights, or None if unsupported (400 code 100 → skip)."""
        resp = self.session.get(
            f"{self.base_url}/{mid}/insights",
            params={'metric': metrics, 'access_token': self.access_token},
        )
        if resp.status_code == 401:
            raise ValueError(
                "Instagram API 401 — token expired/invalid. Action: "
                "Dashboard → Credentials → Meta → new long-lived token."
            )
        if resp.status_code != 200:
            err = resp.json().get('error', {}) if resp.content else {}
            if resp.status_code == 400 and err.get('code') == 100:
                logger.warning(f"Insights unsupported for media {mid} (code 100) — skipped.")
                return None
            raise ValueError(
                f"Instagram insights API {resp.status_code} "
                f"(code {err.get('code', '')}) media {mid}: {err.get('message', '')[:160]}"
            )
        vals = {}
        for item in resp.json().get('data', []):
            series = item.get('values', [])
            vals[item.get('name')] = series[0].get('value', 0) if series else 0
        return {
            'artist_id': self.artist_id, 'media_id': mid, 'date': day,
            'impressions': vals.get('impressions', 0), 'reach': vals.get('reach', 0),
            'engagement': vals.get('engagement', 0), 'saved': vals.get('saved', 0),
            'shares': vals.get('shares', 0),
            'collected_at': datetime.now(timezone.utc),
        }

    @retry(max_attempts=3, backoff="exponential")
    def fetch_media_insights(self, media_ids: list) -> list:
        """Per-media insights; unsupported media are skipped, not fatal."""
        metrics = "impressions,reach,engagement,saved,shares"
        day = datetime.now(timezone.utc).date()
        out = []
        try:
            for mid in media_ids:
                if not mid:
                    continue
                row = self._media_insight_row(mid, metrics, day)
                if row is not None:
                    out.append(row)
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Instagram insights fetch failed: {e}") from e
        logger.info(f"Fetched insights for {len(out)} media item(s)")
        return out

    def save_media_to_db(self, media: list, insights: list) -> None:
        if not self.db:
            raise RuntimeError("Instagram media save: no DB connection")
        if media:
            self.db.upsert_many(
                'instagram_media', media,
                conflict_columns=['artist_id', 'media_id'],
                update_columns=['caption', 'media_type', 'permalink', 'media_url',
                                'timestamp', 'like_count', 'comments_count',
                                'collected_at'],
            )
        if insights:
            self.db.upsert_many(
                'instagram_media_insights', insights,
                conflict_columns=['artist_id', 'media_id', 'date'],
                update_columns=['impressions', 'reach', 'engagement', 'saved',
                                'shares', 'collected_at'],
            )
        logger.info(f"Saved {len(media)} media + {len(insights)} insight row(s)")

    def run(self):
        self._check_proactive_refresh()
        stats = self.fetch_stats()
        self.save_to_db(stats)
        media = self.fetch_media()
        insights = self.fetch_media_insights([m['media_id'] for m in media])
        self.save_media_to_db(media, insights)
        if self.db:
            self.db.close()

if __name__ == "__main__":
    InstagramCollector().run()