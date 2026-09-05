"""Credentials — Spotify connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests

from src.dashboard.utils.i18n import t
from src.utils.platform_probes import (  # la situation que cette sonde nomme
    IDENTITY_MISSING,
    NOT_FOUND,
    UNREACHABLE,
    tagged,
)


def _test_spotify(fields: dict) -> tuple:
    # Spotify uses the client_credentials flow on public catalog data, so a single
    # admin-owned app serves every artist. The artist normally enters nothing: fall
    # back to the app-level env (SPOTIFY_CLIENT_ID/SECRET), mirroring the collector's
    # DB-then-env precedence. A stored per-artist override (if any) still wins.
    client_id     = fields.get('client_id', '').strip() or os.getenv('SPOTIFY_CLIENT_ID', '')
    client_secret = fields.get('client_secret', '').strip() or os.getenv('SPOTIFY_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        return False, t("credentials.spotify.app_not_configured",
                        "App Spotify non configurée côté plateforme "
                        "(SPOTIFY_CLIENT_ID/SECRET) — contactez l'administrateur.")
    try:
        r = requests.post(
            'https://accounts.spotify.com/api/token',
            data={'grant_type': 'client_credentials'},
            auth=(client_id, client_secret),
            timeout=10,
            allow_redirects=False,  # INFO-04: prevent open-redirect SSRF
        )
        data = r.json()
        if not (r.status_code == 200 and data.get('access_token')):
            return False, data.get('error_description', r.text[:150])
        # Connect-time identity validation: confirm the artist's profile actually resolves,
        # so a wrong/empty Spotify ID fails HERE (in the form) instead of silently as 0 rows
        # in spotify_api_daily a day later.
        from ._core import extract_spotify_artist_id
        artist_id = extract_spotify_artist_id(fields.get('spotify_artist_id', ''))
        if not artist_id:
            # The shared app answering is not "connected": without the artist's own ID
            # the collector has no key to collect on. Same class as Meta /me.
            return False, tagged(t("credentials.spotify.artist_missing",
                            "App Spotify OK, mais ton **Spotify Artist ID** n'est pas "
                            "renseigné — sans lui aucune donnée ne peut être collectée. "
                            "Colle l'URL de ta page artiste (open.spotify.com/artist/…)."), IDENTITY_MISSING)
        ra = requests.get(
            f'https://api.spotify.com/v1/artists/{artist_id}',
            headers={'Authorization': f"Bearer {data['access_token']}"},
            timeout=10,
            allow_redirects=False,
        )
        if ra.status_code != 200 or not ra.json().get('id'):
            return False, tagged(t("credentials.spotify.artist_not_found",
                            "Artiste Spotify introuvable : « {aid} ». Colle l'URL de ta "
                            "page Spotify Artist (open.spotify.com/artist/…).").format(aid=artist_id), NOT_FOUND)
        return True, t("credentials.spotify.test_ok_artist",
                       "Connecté — artiste « {name} » ✅").format(name=ra.json().get('name', artist_id))
    except Exception as e:
        # NEVER str(e). This probe passes the shared credential as a QUERY
        # PARAMETER, so a ConnectionError's message embeds the full prepared URL —
        # credential included — and _render.py renders it to the tenant with
        # st.error. A DNS blip was enough to show a non-admin the platform-wide
        # token (Meta, never expires) or the billable API key (YouTube).
        return False, tagged(t("credentials.probe_network_error",
                        "Erreur réseau ({err}) — réessaie dans un instant. Si ça "
                        "persiste, contacte l'administrateur.").format(
                            err=type(e).__name__), UNREACHABLE)
