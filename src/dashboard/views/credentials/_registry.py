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

# Ordered easiest → hardest so a new artist starts where it's quickest (one identifier,
# no third-party app). SoundCloud (user_id) → Spotify (profile URL) → YouTube (channel id)
# → Meta (ad account + asset-sharing). This dict order drives the tabs (router.py) and the
# global KPI (_render.py).
PLATFORMS = {
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
    'spotify': {
        'label': '🎵 Spotify',
        # Central model: the client_credentials app is admin-owned (SPOTIFY_CLIENT_ID/
        # SECRET env, one app serves all artists on public catalog data). The artist
        # supplies ONLY their Spotify artist identity; client_id/secret remain as an
        # optional per-artist override. spotify_artist_id is synced to
        # saas_artists.spotify_artist_id on save (the per-tenant collection key).
        'fields': [
            {'key': 'spotify_artist_id', 'label': 'Spotify Artist ID ou URL profil', 'secret': False},
            {'key': 'client_id',     'label': 'Client ID (optionnel — admin)',     'secret': False},
            {'key': 'client_secret', 'label': 'Client Secret (optionnel — admin)', 'secret': True},
        ],
    },
    'youtube': {
        'label': '🎬 YouTube',
        # Central model: the Data-API key is admin-owned (YOUTUBE_API_KEY env, one Google
        # Cloud key serves all artists). The artist supplies ONLY their Channel ID; api_key
        # remains an optional per-artist override. The connection test validates the
        # channel resolves (a bad UC… 404s the collector, not the key test).
        'fields': [
            {'key': 'channel_id', 'label': 'Channel ID (UC…)',                    'secret': False},
            {'key': 'api_key',    'label': 'API Key (optionnel — admin)',         'secret': True},
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
