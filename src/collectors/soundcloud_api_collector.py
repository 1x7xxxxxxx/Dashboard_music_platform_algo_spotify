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
from src.utils.safe_error import safe_error

# Local-dev convenience only: in containers the env is injected by docker-compose, and
# the mounted /opt/airflow/.env is root-owned 600 (unreadable by the airflow uid) →
# load_dotenv() would raise PermissionError at import and crash the collector. The env
# vars are already present, so a failed/absent .env must be a no-op, never fatal.
try:
    load_dotenv()
except OSError as e:
    logger.debug(f"load_dotenv skipped ({safe_error(e)}); relying on injected environment.")

_TOKEN_ENDPOINT = "https://api.soundcloud.com/oauth2/token"
_API_BASE = "https://api.soundcloud.com"


class SoundCloudCollector:
    def __init__(self, artist_id: int,
                 client_id: str = None,
                 client_secret: str = None,
                 user_id: str = None,
                 refresh_token: str = None):
        self.artist_id = artist_id
        self.client_id = client_id or os.getenv("SOUNDCLOUD_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SOUNDCLOUD_CLIENT_SECRET")
        # TENANT IDENTITY — no env fallback: SOUNDCLOUD_USER_ID is the ADMIN's
        # profile. A collector that cannot be told whose data to fetch must not
        # guess; the caller (DAG) resolves it from artist_credentials.
        self.user_id = (user_id or '').strip()
        if not self.user_id and not self._has_claimed_tracks():
            # L'absence de user_id reste une erreur — SAUF si le locataire a déclaré des
            # titres hébergés ailleurs. Pour un artiste signé sur un label, le profil
            # personnel n'existe pas et n'existera jamais : l'unité collectable est le
            # TITRE, et `GET /tracks/{id}` rend ses écoutes quel que soit le compte qui
            # l'héberge. Refuser de collecter faute de profil revenait à exiger la seule
            # chose qu'il ne peut pas fournir. Mesuré sur le cas GRiNCH, 2026-08-23.
            raise ValueError(
                f"SoundCloudCollector: no user_id for artist_id={artist_id}, and no "
                "claimed track either. Set the User ID in Dashboard → Credentials → "
                "SoundCloud, or declare your tracks on the « ☁️ SoundCloud — "
                "Performance » page, section « Mes titres hébergés sur d'autres "
                "comptes » (moved there 2026-09-04)."
            )
        # Optional OAuth user-token (B2 P2). Absent ⇒ client_credentials mode
        # (unchanged behaviour). Present ⇒ user-context token → real per-track
        # likes. Never raise on absence; it is opt-in per artist.
        self.refresh_token = refresh_token or os.getenv("SOUNDCLOUD_REFRESH_TOKEN")

        if not self.client_id:
            raise ValueError("SOUNDCLOUD_CLIENT_ID manquant — saisir dans Dashboard → Credentials → SoundCloud.")
        if not self.client_secret:
            raise ValueError("SOUNDCLOUD_CLIENT_SECRET manquant — saisir dans Dashboard → Credentials → SoundCloud.")
        if not self.user_id:
            raise ValueError("SOUNDCLOUD_USER_ID manquant — saisir dans Dashboard → Credentials → SoundCloud.")

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self.session = requests.Session()

        # One resolution for the DSN (R33): DATABASE_URL → DATABASE_* → config.yaml.
        # The five os.getenv calls that used to live here defaulted the host to
        # 'localhost', which is wrong inside Airflow — where this collector runs.
        self.db = PostgresHandler.from_env_or_config()

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

    def _get_user_token(self) -> None:
        """OAuth user-token (B2 P2): grant_type=refresh_token.

        Yields a user-context token → the SC API returns real per-track
        likes_count (client_credentials returns 0 for third-party reads).
        SoundCloud rotates the refresh_token on use — the new one MUST be
        persisted or the next run breaks. Non-200 raises (CLAUDE.md #6): no
        silent fallback to client_credentials, which would mask a broken user
        connection and silently restore likes=0.
        """
        r = self.session.post(
            _TOKEN_ENDPOINT,
            data={
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token,
            },
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"SoundCloud refresh_token grant failed: HTTP {r.status_code} "
                f"— {r.text[:200]}. Re-connect SoundCloud in Dashboard → Credentials."
            )
        data = r.json()
        self._access_token = data['access_token']
        expires_in = int(data.get('expires_in', 3600))
        self._token_expires_at = time.time() + expires_in - 60
        new_rt = data.get('refresh_token')
        if new_rt and new_rt != self.refresh_token:
            self.refresh_token = new_rt
            try:
                from src.utils.credential_loader import update_platform_secret
                update_platform_secret(
                    self.artist_id, 'soundcloud', 'refresh_token', new_rt
                )
                logger.info("SoundCloud refresh_token rotated and persisted.")
            except Exception as e:
                logger.warning(
                    "SoundCloud refresh_token rotated but NOT persisted (%s) — "
                    "next run will fail until re-connected.", safe_error(e)
                )
        logger.info("SoundCloud user token obtained (expires in %ds).", expires_in)

    def _ensure_token(self) -> None:
        """Renew token if absent or within 60s of expiry.

        Dual-mode: refresh_token present → user-token (real likes); else the
        client_credentials fallback (unchanged — likes=0 for 3rd-party reads).
        """
        if not self._access_token or time.time() >= self._token_expires_at:
            if self.refresh_token:
                self._get_user_token()
            else:
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
        # Sans user_id, il n'y a pas de profil à parcourir : on va directement aux
        # titres déclarés. Le constructeur a déjà garanti qu'il y en a.
        url = f"{_API_BASE}/users/{self.user_id}/tracks" if self.user_id else None
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
                    # SC returns the like count under `favoritings_count` on
                    # the user-token /tracks response; `likes_count` is 0/absent
                    # there. The spike proved this (read both) — mirror it.
                    'likes_count': int(track.get('likes_count')
                                       or track.get('favoritings_count') or 0),
                    'reposts_count': int(track.get('reposts_count') or 0),
                    'comment_count': int(track.get('comment_count') or 0),
                    # SC API upload timestamp = true release date (None-safe).
                    # entity_period_filter orders "latest release" by this
                    # instead of MIN(collected_at) (= first ingest, not release).
                    'track_created_at': track.get('created_at'),
                    'collected_at': datetime.now(timezone.utc),
                })

            url = data.get('next_href') if collection else None
            page += 1

        if page >= max_pages:
            logger.warning("fetch_tracks: reached max_pages=%d safety cap.", max_pages)

        logger.info("Fetched %d tracks from the profile.", len(tracks_data))
        tracks_data.extend(self.fetch_claimed_tracks(
            already={t['track_id'] for t in tracks_data}))
        logger.info("Fetched %d tracks in total.", len(tracks_data))
        return tracks_data


    def _has_claimed_tracks(self) -> bool:
        """Délègue à `claimed_tracks.has_claimed_tracks` — une seule lecture, un seul
        comportement en cas de table illisible."""
        from src.utils.claimed_tracks import has_claimed_tracks
        return has_claimed_tracks(self.artist_id, "soundcloud",
                                  db=getattr(self, "db", None))

    def fetch_claimed_tracks(self, already: set | None = None) -> list:
        """Tracks this tenant declared that live on somebody else's profile.

        The GRiNCH case: an artist released by a label has `track_count=0` on their
        own profile, so `/users/{id}/tracks` is correctly empty and there is nothing
        to collect. `GET /tracks/{id}` returns the same statistics whatever profile
        hosts the upload, so a declared track is collectable regardless of ownership.

        A claim pointing at a deleted or private track is skipped with a WARNING
        naming the id — one dead row must not lose the others. But an unreadable
        claims table RAISES (rule #6): for an artist released under a label these
        tracks are the only thing to collect, so swallowing that would mean zero rows,
        a SUCCESS exit and an empty dashboard.
        """
        already = already or set()
        # NOT wrapped in a try that returns []. Rule #6, and it earns itself here: for
        # an artist released under a label the claimed tracks are the ONLY thing to
        # collect, so an unreadable claims table would produce zero rows, a SUCCESS
        # exit and an empty dashboard — the exact silent-success shape this whole
        # session is about. Let it raise; the DAG's per-tenant try isolates it.
        from src.utils.claimed_tracks import claimed_track_ids
        ids = [i for i in claimed_track_ids(self.db, self.artist_id, 'soundcloud')
               if i not in already]
        if not ids:
            return []

        self._ensure_token()
        logger.info("Fetching %d claimed track(s) hosted elsewhere…", len(ids))
        out = []
        for track_id in ids:
            try:
                r = self.session.get(
                    f"{_API_BASE}/tracks/{track_id}",
                    headers={'Authorization': f'OAuth {self._access_token}'},
                    timeout=15, allow_redirects=False)
                if r.status_code != 200:
                    # A claim that stopped resolving is worth saying out loud: the
                    # track was deleted or made private, and the artist's numbers
                    # will quietly stop moving otherwise.
                    logger.warning("claimed track %s unreachable: HTTP %s",
                                   track_id, r.status_code)
                    continue
                t = r.json()
                out.append({
                    'artist_id': self.artist_id,
                    'track_id': str(t.get('id')),
                    'title': t.get('title'),
                    'permalink_url': t.get('permalink_url'),
                    'playback_count': int(t.get('playback_count') or 0),
                    'likes_count': int(t.get('likes_count')
                                       or t.get('favoritings_count') or 0),
                    'reposts_count': int(t.get('reposts_count') or 0),
                    'comment_count': int(t.get('comment_count') or 0),
                    'track_created_at': t.get('created_at'),
                    'collected_at': datetime.now(timezone.utc),
                })
            except Exception as e:  # noqa: BLE001 — see docstring
                logger.warning("claimed track %s failed: %s", track_id, type(e).__name__)
        logger.info("Fetched %d claimed track(s).", len(out))
        return out

    def save_to_db(self, tracks: list) -> int:
        """Returns the number of rows written — 0 is a legitimate answer, not a failure.

        The count is what the caller records in `etl_run_log.rows_inserted`. Returning
        None would make "collected nothing" and "did not run" the same value, which is
        precisely the ambiguity the ledger exists to remove.
        """
        if not tracks:
            logger.warning("No tracks to save — skipping.")
            return 0
        self.db.execute_query(
            "DELETE FROM soundcloud_tracks_daily WHERE collected_at::date = CURRENT_DATE AND artist_id = %s",
            (self.artist_id,)
        )
        self.db.insert_many("soundcloud_tracks_daily", tracks)
        logger.info("Saved %d rows to soundcloud_tracks_daily.", len(tracks))
        return len(tracks)

    def run(self) -> int:
        """Returns the number of rows written, for the run ledger."""
        try:
            tracks = self.fetch_tracks()
            return self.save_to_db(tracks)
        finally:
            self.db.close()


if __name__ == "__main__":
    # artist_id is required on the CLI too: the old no-arg form bound the env
    # identity (the admin's) to tenant 1 — the very defect this module now refuses.
    import sys

    if len(sys.argv) < 3:
        sys.exit("usage: soundcloud_api_collector.py <artist_id> <user_id>")
    collector = SoundCloudCollector(artist_id=int(sys.argv[1]), user_id=sys.argv[2])
    collector.run()
