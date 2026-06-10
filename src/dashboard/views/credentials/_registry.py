"""Credentials — platform registry + test/guide dispatch.

Type: Sub
Uses: the four _platform_* modules
The single wiring point: PLATFORMS field definitions, CONNECTION_TESTS map,
and the per-platform guide dispatcher. Pure relocation — no logic change.
"""
from ._platform_spotify import _test_spotify, _guide_spotify
from ._platform_youtube import _test_youtube, _guide_youtube
from ._platform_soundcloud import _test_soundcloud, _guide_soundcloud
from ._platform_meta import _test_meta, _guide_meta


# ─────────────────────────────────────────────
# Platform definitions
# ─────────────────────────────────────────────
# 'secret': True  → stocké dans token_encrypted (Fernet-chiffré)
# 'secret': False → stocké dans extra_config (JSONB, lisible)

PLATFORMS = {
    'spotify': {
        'label': '🎵 Spotify',
        # Collector uses client_credentials only (spotify_api.py) — no
        # redirect_uri / refresh_token needed (those were dormant + misleading).
        'fields': [
            {'key': 'client_id',     'label': 'Client ID',     'secret': False},
            {'key': 'client_secret', 'label': 'Client Secret', 'secret': True},
        ],
    },
    'youtube': {
        'label': '🎬 YouTube',
        # Collector uses a static Data-API key (youtube_collector.py
        # developerKey) + channel_id — NOT OAuth. The old client_id/
        # client_secret/refresh_token fields were dormant and made per-tenant
        # config impossible (no api_key field at all).
        'fields': [
            {'key': 'api_key',    'label': 'API Key (YouTube Data API v3)', 'secret': True},
            {'key': 'channel_id', 'label': 'Channel ID (UC…)',             'secret': False},
        ],
    },
    'soundcloud': {
        'label': '☁️ SoundCloud',
        # Artist provides only their numeric user_id; the app credentials
        # (client_id/client_secret) come from the shared env app, not per-artist.
        # The optional OAuth real-likes path is an admin runbook (mint script),
        # not exposed in the artist form.
        'fields': [
            {'key': 'user_id', 'label': 'User ID numérique (ex: 377065610)', 'secret': False},
        ],
    },
    'meta': {
        'label': '📱 Meta / Instagram',
        # Shared System User app (access_token/app_id/app_secret) comes from the
        # platform env; the artist provides only their own Ad Account ID. Instagram
        # is admin-configured (env). Stored per-artist app creds still take
        # precedence in the collector if present.
        'fields': [
            {'key': 'account_id', 'label': 'Ad Account ID (act_… ou numérique)', 'secret': False},
        ],
    },
}


CONNECTION_TESTS = {
    'spotify':    _test_spotify,
    'youtube':    _test_youtube,
    'soundcloud': _test_soundcloud,
    'meta':       _test_meta,
}


def _render_platform_guide(platform_key: str) -> None:
    """Render a detailed, platform-specific credential guide."""
    guides = {
        'soundcloud': _guide_soundcloud,
        'meta':       _guide_meta,
        'spotify':    _guide_spotify,
        'youtube':    _guide_youtube,
    }
    fn = guides.get(platform_key)
    if not fn:
        return
    fn()
