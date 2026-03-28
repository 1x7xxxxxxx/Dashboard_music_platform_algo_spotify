"""Unit tests — silent success regression suite for collectors.

Verifies that every collector raises on API errors instead of returning
empty data. Any return of None / [] / {} in an except block is a P2
data-integrity bug that marks DAG tasks SUCCESS with 0 rows.

Coverage:
- SpotifyCollector.get_artist_info        → generic Exception
- SpotifyCollector.get_artist_top_tracks  → generic Exception
- YouTubeCollector.get_channel_stats      → generic Exception
- YouTubeCollector.get_channel_videos     → generic Exception
- YouTubeCollector.get_video_stats        → generic Exception
- SoundCloudCollector.fetch_tracks        → 401 / 403 / non-200
- InstagramCollector.fetch_stats          → 401 / 400 / network error
"""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Stub heavy optional dependencies not installed in the local venv.
# These are always present inside Docker; locally we only need the interface.
# ─────────────────────────────────────────────────────────────────────────────

def _stub_module(name: str):
    """Insert a MagicMock as a top-level module (and all its dotted parents)."""
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        key = ".".join(parts[:i])
        if key not in sys.modules:
            sys.modules[key] = MagicMock()


for _mod in ["spotipy", "spotipy.oauth2", "googleapiclient", "googleapiclient.discovery"]:
    _stub_module(_mod)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_response(status_code: int, json_data: dict | None = None, text: str = "error"):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.text = text
    return r


# ─────────────────────────────────────────────────────────────────────────────
# SpotifyCollector
# ─────────────────────────────────────────────────────────────────────────────

class TestSpotifyCollectorErrors:

    def _collector(self):
        from src.collectors.spotify_api import SpotifyCollector
        c = SpotifyCollector.__new__(SpotifyCollector)
        c.sp = MagicMock()
        return c

    def test_get_artist_info_raises_on_api_error(self):
        c = self._collector()
        c.sp.artist.side_effect = Exception("401 Unauthorized")
        with pytest.raises(Exception, match="401"):
            c.get_artist_info("fake_id")

    def test_get_artist_info_never_returns_none_on_error(self):
        """Regression: previous code returned None on exception."""
        c = self._collector()
        c.sp.artist.side_effect = Exception("network timeout")
        with pytest.raises(Exception):
            result = c.get_artist_info("fake_id")
            assert result is not None, "Silent success: returned None instead of raising"

    def test_get_artist_top_tracks_raises_on_api_error(self):
        c = self._collector()
        c.sp.artist_top_tracks.side_effect = Exception("403 Forbidden")
        with pytest.raises(Exception, match="403"):
            c.get_artist_top_tracks("fake_id")

    def test_get_artist_top_tracks_never_returns_empty_list_on_error(self):
        """Regression: previous code returned [] on exception."""
        c = self._collector()
        c.sp.artist_top_tracks.side_effect = Exception("timeout")
        with pytest.raises(Exception):
            result = c.get_artist_top_tracks("fake_id")
            assert result != [], "Silent success: returned [] instead of raising"


# ─────────────────────────────────────────────────────────────────────────────
# YouTubeCollector
# ─────────────────────────────────────────────────────────────────────────────

class TestYouTubeCollectorErrors:

    def _collector(self):
        from src.collectors.youtube_collector import YouTubeCollector
        c = YouTubeCollector.__new__(YouTubeCollector)
        c.youtube = MagicMock()
        return c

    def test_get_channel_stats_raises_on_api_error(self):
        c = self._collector()
        c.youtube.channels.return_value.list.return_value.execute.side_effect = Exception("quota exceeded")
        with pytest.raises(Exception, match="quota"):
            c.get_channel_stats("UC_fake")

    def test_get_channel_stats_never_returns_none_on_error(self):
        """Regression: previous code returned None on exception."""
        c = self._collector()
        c.youtube.channels.return_value.list.return_value.execute.side_effect = Exception("error")
        with pytest.raises(Exception):
            result = c.get_channel_stats("UC_fake")
            assert result is not None, "Silent success: returned None instead of raising"

    def test_get_channel_videos_raises_on_api_error(self):
        c = self._collector()
        c.youtube.channels.return_value.list.return_value.execute.side_effect = Exception("503")
        with pytest.raises(Exception):
            c.get_channel_videos("UC_fake")

    def test_get_video_stats_raises_on_api_error(self):
        c = self._collector()
        c.youtube.videos.return_value.list.return_value.execute.side_effect = Exception("invalid key")
        with pytest.raises(Exception, match="invalid key"):
            c.get_video_stats(["vid1", "vid2"])


# ─────────────────────────────────────────────────────────────────────────────
# SoundCloudCollector
# ─────────────────────────────────────────────────────────────────────────────

class TestSoundCloudCollectorErrors:

    def _collector(self):
        from src.collectors.soundcloud_api_collector import SoundCloudCollector
        c = SoundCloudCollector.__new__(SoundCloudCollector)
        c.client_id = "fake_client_id"
        c.client_secret = "fake_secret"
        c.user_id = "123456789"
        c.artist_id = 1
        c.base_url = "https://api-v2.soundcloud.com"
        c.db = MagicMock()
        c._access_token = "valid_token"           # skip _get_access_token in _ensure_token
        c._token_expires_at = float("inf")        # token never expires during test
        c.session = MagicMock()
        return c

    def test_fetch_tracks_raises_valueerror_on_401(self):
        c = self._collector()
        c.session.get.return_value = _mock_response(401)
        with pytest.raises(ValueError, match="401"):
            c.fetch_tracks()

    def test_fetch_tracks_raises_on_403(self):
        c = self._collector()
        c.session.get.return_value = _mock_response(403)
        with pytest.raises((ValueError, RuntimeError), match="403"):
            c.fetch_tracks()

    def test_fetch_tracks_raises_on_non_200(self):
        c = self._collector()
        c.session.get.return_value = _mock_response(500, text="Internal Server Error")
        with pytest.raises((ValueError, RuntimeError), match="500"):
            c.fetch_tracks()

    def test_fetch_tracks_never_returns_empty_list_on_401(self):
        """Regression: before fix, 401 was swallowed by outer except → returned []."""
        c = self._collector()
        c.session.get.return_value = _mock_response(401)
        with pytest.raises((ValueError, RuntimeError)):
            result = c.fetch_tracks()
            assert result != [], "Silent success regression: returned [] on 401"


# ─────────────────────────────────────────────────────────────────────────────
# InstagramCollector
# ─────────────────────────────────────────────────────────────────────────────

class TestInstagramCollectorErrors:

    def _collector(self):
        from src.collectors.instagram_api_collector import InstagramCollector
        c = InstagramCollector.__new__(InstagramCollector)
        c.access_token = "fake_token"
        c.ig_user_id = "17841402151518986"
        c.artist_id = 1
        c.base_url = "https://graph.facebook.com/v18.0"
        c.db = MagicMock()
        # Use MagicMock session — fetch_stats calls self.session.get()
        c.session = MagicMock()
        return c

    def test_fetch_stats_raises_valueerror_on_401(self):
        c = self._collector()
        c.session.get.return_value = _mock_response(
            401, json_data={"error": {"message": "Invalid OAuth access token"}}
        )
        with pytest.raises(ValueError, match="401"):
            c.fetch_stats()

    def test_fetch_stats_raises_valueerror_on_400(self):
        c = self._collector()
        c.session.get.return_value = _mock_response(
            400, json_data={"error": {"message": "not a Business account", "code": 0}}
        )
        with pytest.raises(ValueError, match="400"):
            c.fetch_stats()

    def test_fetch_stats_raises_on_network_error(self):
        import requests as req
        c = self._collector()
        c.session.get.side_effect = req.exceptions.ConnectionError("connection refused")
        with pytest.raises((RuntimeError, Exception)):
            c.fetch_stats()
