"""A tenant's stored copy of a CENTRAL app secret never outranks the rotated one.

Type: Sub
Uses: src/utils/credential_loader.py (`central_app_wins`)
Depends on: nothing — the credentials and the environment are fabricated
Persists in: nothing

Measured in production on 2026-09-26: after R177 rotated `META_APP_SECRET`, artist 1's
stored credentials still carried the OLD central `app_secret`; every reader does
`creds.get('app_secret') or env`, the stale copy won, and Meta answered
`#100 Invalid appsecret_proof` — collection down for the tenant the morning after.
"""
from __future__ import annotations

from src.utils.credential_loader import central_app_wins

_ENV = {"META_APP_ID": "2200", "META_APP_SECRET": "new-secret",  # pragma: allowlist secret
        "SPOTIFY_CLIENT_ID": "sp", "SPOTIFY_CLIENT_SECRET": "sp-new"}  # pragma: allowlist secret


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the production shape — the central app's id with the OLD secret —
    resolves to the rotated secret; a tenant's OWN app keeps its own secret; a platform
    with no central app, and credentials with no stored secret, are left alone."""
    stale = {"app_id": "2200", "app_secret": "old-secret", "account_id": "act_1"}  # pragma: allowlist secret
    assert central_app_wins("meta", stale, _ENV)["app_secret"] == "new-secret"  # pragma: allowlist secret
    no_id = {"app_secret": "old-secret"}  # pragma: allowlist secret
    assert central_app_wins("meta", no_id, _ENV)["app_secret"] == "new-secret"  # pragma: allowlist secret
    own = {"app_id": "9999", "app_secret": "tenant-secret"}  # pragma: allowlist secret
    assert central_app_wins("meta", own, _ENV)["app_secret"] == "tenant-secret"  # pragma: allowlist secret
    spotify = {"client_id": "sp", "client_secret": "sp-old"}  # pragma: allowlist secret
    assert central_app_wins("spotify", spotify, _ENV)["client_secret"] == "sp-new"  # pragma: allowlist secret
    youtube = {"api_key": "artist-own-key"}  # pragma: allowlist secret
    assert central_app_wins("youtube", youtube, _ENV) == youtube
    assert central_app_wins("meta", {"account_id": "act_1"}, _ENV) == {"account_id": "act_1"}


def test_an_unset_central_secret_never_erases_a_stored_one() -> None:
    """If the environment has no central secret, the stored value is all there is."""
    stored = {"app_id": "2200", "app_secret": "only-copy"}  # pragma: allowlist secret
    assert central_app_wins("meta", stored, {"META_APP_ID": "2200"}) == stored


def test_an_unset_central_id_never_hands_the_central_secret_to_another_app() -> None:
    """Security review 2026-09-26: with `META_APP_ID` missing, a stored id cannot be
    compared — the tenant's own secret must stay."""
    own = {"app_id": "9999", "app_secret": "tenant-secret"}  # pragma: allowlist secret
    assert central_app_wins("meta", own, {"META_APP_SECRET": "new-secret"}) == own  # pragma: allowlist secret
