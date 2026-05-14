"""SoundCloud API collector — OAuth 2.0 Client Credentials.

Type: Feature
Uses: PostgresHandler, retry
Persists in: soundcloud_tracks_daily
"""
import os
import sys
import time
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler
from src.utils.retry import retry

load_dotenv()

_TOKEN_ENDPOINT = "https://api.soundcloud.com/oauth2/token"
_API_BASE = "https://api.soundcloud.com"


class SoundCloudCollector:
    def __init__(self, artist_id: int = 1,
                 client_id: str = None,
                 client_secret: str = None,
                 user_id: str = None):
        self.artist_id = artist_id
        self.client_id = client_id or os.getenv("SOUNDCLOUD_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SOUNDCLOUD_CLIENT_SECRET")
        self.user_id = user_id or os.getenv("SOUNDCLOUD_USER_ID")

        self.db_host = os.getenv('DATABASE_HOST', 'localhost')
        self.db_port = os.getenv('DATABASE_PORT', '5432')
        self.db_name = os.getenv('DATABASE_NAME')
        self.db_user = os.getenv('DATABASE_USER')
        self.db_pass = os.getenv('DATABASE_PASSWORD')

        if not self.client_id:
            raise ValueError("SOUNDCLOUD_CLIENT_ID manquant — saisir dans Dashboard → Credentials → SoundCloud.")
        if not self.client_secret:
            raise ValueError("SOUNDCLOUD_CLIENT_SECRET manquant — saisir dans Dashboard → Credentials → SoundCloud.")
        if not self.user_id:
            raise ValueError("SOUNDCLOUD_USER_ID manquant — saisir dans Dashboard → Credentials → SoundCloud.")

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self.session = requests.Session()

        self.db = PostgresHandler(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=self.db_pass
        )

    def _get_access_token(self) -> None:
        """Fetch a new OAuth access token via Client Credentials grant."""
        r = self.session.post(
            _TOKEN_ENDPOINT,
            data={
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            },
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"SoundCloud OAuth token request failed: HTTP {r.status_code} — {r.text[:200]}"
            )
        data = r.json()
        self._access_token = data['access_token']
        expires_in = int(data.get('expires_in', 3600))
        self._token_expires_at = time.time() + expires_in - 60  # 60s safety margin
        logger.info("SoundCloud access token obtained (expires in %ds).", expires_in)

    def _ensure_token(self) -> None:
        """Renew token if absent or within 60s of expiry."""
        if not self._access_token or time.time() >= self._token_expires_at:
            self._get_access_token()

    @retry(max_attempts=3, backoff="exponential")
    def fetch_tracks(self) -> list:
        """Fetch all tracks for self.user_id via the official SoundCloud API.

        Follows cursor-based pagination via next_href — never increments offset
        manually, which would cause an infinite loop when the API uses cursors.
        Capped at 200 pages (~10 000 tracks) as a safety guard.
        """
        self._ensure_token()
        logger.info("Fetching SoundCloud tracks for user %s...", self.user_id)

        tracks_data = []
        url = f"{_API_BASE}/users/{self.user_id}/tracks"
        params: dict = {'limit': 50, 'linked_partitioning': 1}
        max_pages = 200
        page = 0

        while url and page < max_pages:
            r = self.session.get(
                url,
                headers={'Authorization': f'OAuth {self._access_token}'},
                params=params,
                timeout=15,
            )
            params = {}  # next_href already contains all query params

            if r.status_code == 401:
                raise ValueError(
                    "SoundCloud API 401 — access token rejected. "
                    "Verify client_id and client_secret in Dashboard → Credentials → SoundCloud."
                )
            if r.status_code == 429:
                retry_after = r.headers.get('Retry-After', '?')
                raise ValueError(
                    f"SoundCloud API 429 — rate limit hit (Retry-After: {retry_after}s). "
                    "Airflow retry_delay=10min will handle it."
                )
            if r.status_code != 200:
                raise RuntimeError(f"SoundCloud API {r.status_code}: {r.text[:200]}")

            data = r.json()
            collection = data.get('collection', [])
            for track in collection:
                tracks_data.append({
                    'artist_id': self.artist_id,
                    'track_id': str(track.get('id')),
                    'title': track.get('title'),
                    'permalink_url': track.get('permalink_url'),
                    'playback_count': int(track.get('playback_count') or 0),
                    'likes_count': int(track.get('likes_count') or 0),
                    'reposts_count': int(track.get('reposts_count') or 0),
                    'comment_count': int(track.get('comment_count') or 0),
                    'collected_at': datetime.now(timezone.utc),
                })

            url = data.get('next_href') if collection else None
            page += 1

        if page >= max_pages:
            logger.warning("fetch_tracks: reached max_pages=%d safety cap.", max_pages)

        logger.info("Fetched %d tracks.", len(tracks_data))
        return tracks_data

    def save_to_db(self, tracks: list) -> None:
        if not tracks:
            logger.warning("No tracks to save — skipping.")
            return
        self.db.execute_query(
            "DELETE FROM soundcloud_tracks_daily WHERE collected_at::date = CURRENT_DATE AND artist_id = %s",
            (self.artist_id,)
        )
        self.db.insert_many("soundcloud_tracks_daily", tracks)
        logger.info("Saved %d rows to soundcloud_tracks_daily.", len(tracks))

    def run(self) -> None:
        try:
            tracks = self.fetch_tracks()
            self.save_to_db(tracks)
        finally:
            self.db.close()


if __name__ == "__main__":
    collector = SoundCloudCollector()
    collector.run()
