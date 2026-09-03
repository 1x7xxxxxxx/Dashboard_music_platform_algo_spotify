"""Turn a link an artist already has into the identifier the pipeline needs.

Type: Utility
Uses: requests (lazy), os — no streamlit, no DB, so a DAG or a CLI can import it
Triggers: credentials views, tools/artist_preflight.py
Persists in: nothing

Why this module exists — measured 2026-09-03.

**SoundCloud is the only platform that had no path from a link to its identifier**,
and the first draft of this module got that wrong by adding two it did not need.

What the guide asks of a SoundCloud artist today: open `/discover`, view the page
**source** (`Ctrl+U`), search for `soundcloud:users:`, copy the digits. That is a
developer's gesture, and `runbook-artist-test-session.md:127` says so in writing —
*« YouTube … et SoundCloud (afficher le code source d'une page) ne sont pas des gestes
d'artiste. Attends-toi à les faire AVEC lui, en partage d'écran. »*

The other two already had one, which is why they are NOT here:

* **Spotify** — `views/credentials/_core.py::extract_spotify_artist_id` already takes
  the profile URL straight from the field, whose label reads « Spotify Artist ID **ou
  URL profil** ».
* **YouTube** — `_platform_youtube.py` resolves a `@handle` and then **reports** the
  `UC…` id for the artist to paste, rather than substituting it. That is a deliberate
  choice recorded on the spot: *« never substitute it silently: a tenant's identity is
  not inferred here »*. Adding a second, silent path would have overturned a decision
  by accident.

Duplicating either would have created two implementations of one rule — the shape
that drifts.

The mechanism was already in the repo for a neighbouring case:
`views/credentials/_render.py::_resolve_soundcloud_track` calls SoundCloud's official
`/resolve` endpoint, and its own comment notes that *"`/resolve` happily returns a
USER for a profile URL"* — the exact capability the SoundCloud step needed, sitting
unused two functions away.

## Why this is server-side and not a script on the artist's machine

The question that prompted this was whether to ship a helper the artist runs locally.
They do not need one: every lookup below reads a **public** page or a public API with
the platform's *shared* app credentials. Nothing here touches the artist's own login,
so there is no credential to capture, nothing to install, nothing to sign, and no
binary to support across Windows and macOS. A server-side resolver is strictly less
machinery for strictly more reach.

This is unrelated to ADR-004, which rejected automating **Spotify for Artists**: that
one requires the artist's SSO session and violates Spotify's terms. Reading a public
profile URL does neither.

## The one that cannot be done this way

**Meta ad account id.** It lives inside the artist's Business Manager, is not public,
and no shared credential can reach it. It stays a manual step, and saying so is the
honest answer rather than pretending symmetry.
"""
from __future__ import annotations

import os

_SC_TOKEN_URL = "https://api.soundcloud.com/oauth2/token"
_SC_RESOLVE_URL = "https://api.soundcloud.com/resolve"

# Every network call carries one. `youtube_collector` shipped without any for months
# and its @retry could not see the resulting hang, because httplib2 raises neither of
# the two exceptions `src/utils/retry.py` retries (class
# `timeout-bounds-the-socket-not-the-call`). A resolver called from a form must fail
# fast rather than hold the page.
_TIMEOUT = 15


class ResolutionError(RuntimeError):
    """The lookup could not be performed. Carries a CODE, not a rendered sentence.

    Deliberately not a silent `None`: a resolver that answers "nothing" for both "this
    is not your profile" and "our app credentials are missing" sends the artist to
    re-check a URL that was correct (`broken-probe-rendered-as-user-fault`).

    And deliberately a code rather than a message. Two reasons, in order of weight:

    1. `tests/test_credentials_security.py::test_no_probe_surfaces_a_whole_exception`
       forbids any caught exception reaching the UI from a credentials module — those
       modules pass credentials in query strings, so an exception's text can carry
       one. The guard cannot tell an authored sentence from a leaked URL, and it
       should not have to: nothing built from an exception goes on screen.
    2. A sentence hardcoded in `src/utils/` bypasses the i18n catalog entirely and
       would render French to an English reader. A code lets the view call `t()`.
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# The whole vocabulary, in one place. A view maps these to `t("credentials.resolve.<code>")`;
# the English half lives in `i18n_catalog/credentials.py` like every other string.
RESOLUTION_CODES = (
    "empty",            # nothing pasted
    "app_not_configured",   # OUR credentials are missing — not the artist's fault
    "token_refused",        # the platform would not issue a token — not their fault
    "not_found",            # the platform does not know this link
    "upstream_error",       # any other non-200
    "is_a_track",           # resolved, but to a track rather than a profile
)


# ── SoundCloud — the official /resolve endpoint, shared app credentials ─────

def _soundcloud_token() -> str:
    """A client-credentials token for the PLATFORM's app, never the artist's."""
    import requests

    cid = os.getenv("SOUNDCLOUD_CLIENT_ID", "")
    sec = os.getenv("SOUNDCLOUD_CLIENT_SECRET", "")
    if not cid or not sec:
        raise ResolutionError("app_not_configured")
    r = requests.post(
        _SC_TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": cid,
              "client_secret": sec},
        timeout=_TIMEOUT, allow_redirects=False)
    token = r.json().get("access_token") if r.status_code == 200 else None
    if not token:
        raise ResolutionError("token_refused")
    return token


def soundcloud_user_id_from_url(url: str) -> tuple[str, str]:
    """`(user_id, permalink)` for a public SoundCloud profile URL.

    Replaces the "view page source, search `soundcloud:users:`" step of the guide.
    `/resolve` returns a `kind` and we check it: a TRACK url resolves happily too, and
    storing a track id in a column that means "user id" would be silent and permanent
    — the mirror of the check `_resolve_soundcloud_track` already makes in the other
    direction.
    """
    import requests

    cleaned = (url or "").strip()
    if not cleaned:
        raise ResolutionError("empty")
    if not cleaned.startswith("http"):
        cleaned = f"https://soundcloud.com/{cleaned.lstrip('/')}"

    r = requests.get(
        _SC_RESOLVE_URL,
        headers={"Authorization": f"OAuth {_soundcloud_token()}"},
        params={"url": cleaned}, timeout=_TIMEOUT, allow_redirects=True)
    if r.status_code == 404:
        raise ResolutionError("not_found")
    if r.status_code != 200:
        raise ResolutionError("upstream_error")
    data = r.json()
    if data.get("kind") != "user":
        raise ResolutionError("is_a_track")
    return str(data.get("id")), str(data.get("permalink") or "")


# What each platform can and cannot resolve from a link, in one place so a view, a
# test and a guide cannot disagree about it. Meta is present ON PURPOSE, saying no:
# an omission reads as an oversight, a declared `False` reads as a decision.
RESOLVED_HERE: dict[str, bool] = {
    "soundcloud": True,   # this module
    "spotify": False,     # already handled by _core.extract_spotify_artist_id
    "youtube": False,     # already handled by _platform_youtube (resolve-and-report)
    "meta": False,        # ad account id lives inside Business Manager, never public
    "instagram": False,   # ig_user_id comes from the Meta graph, not from a page
}
