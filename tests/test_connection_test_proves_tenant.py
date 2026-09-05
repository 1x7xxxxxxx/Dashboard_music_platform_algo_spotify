"""Guard — a green "Tester la connexion" must prove THIS tenant's data path.

Error class `connection-test-proves-app-not-tenant`: every platform credential
test used to validate the admin-owned shared app (Spotify client_credentials,
YouTube API key, Meta /me, SoundCloud OAuth token) and return ✅ without ever
touching the artist's own identifier. The artist then saw "Connecté", the DAG
exited SUCCESS with 0 rows, and the view stayed empty for a day — the
silent-success class (CLAUDE.md rule #6) moved one layer up, into the form.

Observed twice in beta: Benken (Meta ad account never shared, YouTube channel
empty) and Grinch 2026-08-12 (SoundCloud "correctement configuré", zero data).

Each test below asserts the failing half: shared app OK + tenant identity
missing/empty ⇒ ok is False and the message names the next action.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.dashboard.views.credentials._platform_meta import _test_instagram, _test_meta
from src.dashboard.views.credentials._platform_soundcloud import _test_soundcloud
from src.dashboard.views.credentials._platform_spotify import _test_spotify
from src.dashboard.views.credentials._platform_youtube import _test_youtube


def _resp(status=200, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.text = str(payload)
    return r


# ── SoundCloud — the Grinch symptom ──────────────────────────────────────────

@patch("src.dashboard.views.credentials._platform_soundcloud.requests")
def test_soundcloud_zero_public_tracks_is_a_failure(mock_requests):
    """user_id resolves (HTTP 200) but exposes no track → nothing to collect."""
    mock_requests.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret
    mock_requests.get.return_value = _resp(200, {"collection": []})

    ok, msg = _test_soundcloud({"user_id": "377065610", "client_id": "cid",
                                "client_secret": "sec"})  # pragma: allowlist secret

    assert ok is False
    assert "aucun titre public" in msg.lower()


@patch("src.dashboard.views.credentials._platform_soundcloud.requests")
def test_soundcloud_with_tracks_still_passes(mock_requests):
    mock_requests.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret
    mock_requests.get.return_value = _resp(200, {"collection": [{"id": 1}]})

    ok, _ = _test_soundcloud({"user_id": "377065610", "client_id": "cid",
                              "client_secret": "sec"})  # pragma: allowlist secret

    assert ok is True


# ── Meta — the Benken asset-sharing gap ──────────────────────────────────────

@patch("src.dashboard.views.credentials._platform_meta.requests")
def test_meta_shared_token_alone_is_not_connected(mock_requests):
    """/me green + no account_id must NOT read as connected."""
    mock_requests.get.return_value = _resp(200, {"id": "1", "name": "System User"})

    ok, msg = _test_meta({"access_token": "tok"})  # pragma: allowlist secret

    assert ok is False
    assert "Ad Account ID" in msg


@patch("src.dashboard.views.credentials._platform_meta.requests")
def test_meta_unshared_ad_account_is_a_failure(mock_requests):
    """The account exists but was never shared with the app → Graph errors."""
    mock_requests.get.side_effect = [
        _resp(200, {"id": "1", "name": "System User"}),
        _resp(400, {"error": {"message": "Object does not exist"}}),
    ]

    ok, msg = _test_meta({"access_token": "tok", "account_id": "65390907"})  # pragma: allowlist secret

    assert ok is False
    assert "act_65390907" in msg
    assert "partagé" in msg  # names the asset-sharing fix


@patch("src.dashboard.views.credentials._platform_meta.requests")
def test_meta_shared_ad_account_passes(mock_requests):
    mock_requests.get.side_effect = [
        _resp(200, {"id": "1", "name": "System User"}),
        _resp(200, {"id": "act_65390907", "name": "Benken Ads", "account_status": 1}),
    ]

    ok, msg = _test_meta({"access_token": "tok", "account_id": "act_65390907"})  # pragma: allowlist secret

    assert ok is True
    assert "Benken Ads" in msg


# ── YouTube — key-only green, and the empty-channel case ─────────────────────

@patch("src.dashboard.views.credentials._platform_youtube.requests")
def test_youtube_valid_key_without_channel_is_a_failure(mock_requests):
    mock_requests.get.return_value = _resp(200, {"items": [{"id": "fr"}]})

    ok, msg = _test_youtube({"api_key": "AIzaKey"})  # pragma: allowlist secret

    assert ok is False
    assert "Channel ID" in msg


@patch("src.dashboard.views.credentials._platform_youtube.requests")
def test_youtube_empty_channel_is_a_failure(mock_requests):
    mock_requests.get.side_effect = [
        _resp(200, {"items": [{"id": "fr"}]}),                       # key probe
        _resp(200, {"items": [{"statistics": {"videoCount": "0"}}]}),  # channel probe
    ]

    ok, msg = _test_youtube({"api_key": "AIzaKey", "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw"})  # pragma: allowlist secret

    assert ok is False
    assert "Topic" in msg  # points at the auto-generated distribution channel


@patch("src.dashboard.views.credentials._platform_youtube.requests")
def test_youtube_channel_with_videos_passes(mock_requests):
    mock_requests.get.side_effect = [
        _resp(200, {"items": [{"id": "fr"}]}),
        _resp(200, {"items": [{"statistics": {"videoCount": "42"}}]}),
    ]

    ok, msg = _test_youtube({"api_key": "AIzaKey", "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw"})  # pragma: allowlist secret

    assert ok is True
    assert "42" in msg


# ── Spotify — shared client_credentials app is not an identity ───────────────

@patch("src.dashboard.views.credentials._platform_spotify.requests")
def test_spotify_app_without_artist_id_is_a_failure(mock_requests):
    mock_requests.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret

    ok, msg = _test_spotify({"client_id": "cid", "client_secret": "sec"})  # pragma: allowlist secret

    assert ok is False
    assert "Artist ID" in msg


@patch("src.dashboard.views.credentials._platform_spotify.requests")
def test_spotify_resolved_artist_passes(mock_requests):
    mock_requests.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret
    mock_requests.get.return_value = _resp(200, {"id": "3TVXtAsR1Inumwj472S9r4",
                                                 "name": "Drake"})

    ok, msg = _test_spotify({
        "client_id": "cid", "client_secret": "sec",  # pragma: allowlist secret
        "spotify_artist_id": "https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4",
    })

    assert ok is True
    assert "Drake" in msg


# ── The class itself: no platform may pass on shared-app credentials alone ───

@pytest.mark.parametrize("case", [
    ("soundcloud", _test_soundcloud, {"client_id": "cid", "client_secret": "sec"}),  # pragma: allowlist secret
    ("spotify", _test_spotify, {"client_id": "cid", "client_secret": "sec"}),  # pragma: allowlist secret
    ("youtube", _test_youtube, {"api_key": "AIzaKey"}),  # pragma: allowlist secret
    ("meta", _test_meta, {"access_token": "tok"}),  # pragma: allowlist secret
    ("meta", _test_instagram, {"access_token": "tok"}),  # pragma: allowlist secret
])
def test_no_platform_passes_without_tenant_identity(case):
    """Whatever the platform, an artist who provided nothing is not connected."""
    name, fn, app_only_fields = case
    module = f"src.dashboard.views.credentials._platform_{name}"
    with patch(f"{module}.requests") as mock_requests:
        mock_requests.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret
        mock_requests.get.return_value = _resp(200, {"id": "1", "name": "app",
                                                     "items": [{"id": "fr"}],
                                                     "collection": []})
        ok, _ = fn(app_only_fields)
    assert ok is False, f"{name}: shared app alone must not read as connected"


# ── Coverage: a platform with no probe at all is the same class, one step earlier ──

def test_every_logical_platform_has_a_connection_test():
    """Instagram had none, and that is why nobody ever got a verdict on it.

    Coverage used to be judged against the four form TABS, which Instagram is not —
    its id is a field of the Meta tab. So the platform that readiness tracks, the
    alert monitor watches and the canary should exercise was tested only as an
    optional suffix inside `_test_meta`, silently skipped when the id was blank.
    `tools/artist_preflight.py` step 3 iterates CONNECTION_TESTS, so the gate that
    runs before every artist session never probed it.
    """
    from src.dashboard.views.credentials._registry import CONNECTION_TESTS
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    missing = set(PLATFORM_IDENTITIES) - set(CONNECTION_TESTS)
    assert not missing, (
        f"{sorted(missing)} can be declared by an artist but has no connection test — "
        f"there is no way for them to learn it is wrong before the data does not arrive"
    )


def test_instagram_refuses_a_blank_identity():
    """Never True on a missing id: that is the whole contract of this file."""
    ok, msg = _test_instagram({"access_token": "tok"})  # pragma: allowlist secret
    assert ok is False
    assert "Instagram Business Account ID" in msg, msg


# ── La sonde doit poser la QUESTION DU COLLECTEUR ────────────────────────────
# Ajouté le 2026-09-05, après qu'un artiste a lu « aucun titre public » sur un
# profil qui en a DIX-SEPT, pendant que la collecte les ramenait.
#
# Mesuré sur `users/377065610` avec le jeton d'application, `linked_partitioning=1` :
#
#     limit=1  → 0 titre      limit=5  → 4      limit=50 → 17
#     limit=2  → 1 titre      limit=10 → 8
#
# SoundCloud filtre certains titres APRÈS avoir appliqué la limite. La sonde
# demandait une page de 1 et concluait « profil vide » ; le collecteur demande 50.
# Une sonde qui ne pose pas la question du collecteur ne prédit pas son résultat.

def test_the_probe_asks_for_the_same_page_as_the_collector():
    """Le nombre est ÉPINGLÉ des deux côtés, pas la constante d'un seul.

    Lecture par AST : le commentaire ci-dessus contient `limit=1`, donc une
    recherche de chaîne serait rouge sur sa propre explication.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    def _limits(path: Path, needle: str) -> set:
        found = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Dict):
                continue
            keys = {k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if needle not in keys:
                continue
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and k.value == "limit"
                        and isinstance(v, ast.Constant)):
                    found.add(v.value)
        return found

    probe = _limits(root / "src/dashboard/views/credentials/_platform_soundcloud.py",
                    "linked_partitioning")
    collector = _limits(root / "src/collectors/soundcloud_api_collector.py",
                        "linked_partitioning")

    assert probe, "la sonde n'a plus de page paginée"
    assert collector, "le collecteur n'a plus de page paginée"
    assert probe == collector, (
        f"la sonde demande {probe} et le collecteur {collector} : elles ne posent "
        "pas la même question, donc la sonde ne prédit pas ce que la collecte fera")
    # Et jamais 1 : c'est la valeur qui rend 0 sur un profil qui a 17 titres.
    assert 1 not in probe


@patch("src.dashboard.views.credentials._platform_soundcloud.requests")
def test_an_empty_first_page_with_a_next_page_is_not_an_empty_profile(mock_requests):
    """Une page vide AVEC `next_href` ne prouve rien — on ne l'annonce pas comme vide."""
    mock_requests.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret
    mock_requests.get.return_value = _resp(
        200, {"collection": [], "next_href": "https://api.soundcloud.com/next"})

    ok, msg = _test_soundcloud({"user_id": "377065610", "client_id": "cid",
                                "client_secret": "sec"})  # pragma: allowlist secret

    assert ok is True, "un profil dont la plateforme annonce d'autres pages est dit vide"
    assert "aucun titre public" not in msg.lower()


@patch("src.dashboard.views.credentials._platform_soundcloud.requests")
def test_a_truly_empty_profile_is_still_a_failure(mock_requests):
    """Le garde ci-dessus ne doit pas rendre la sonde complaisante."""
    mock_requests.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret
    mock_requests.get.return_value = _resp(200, {"collection": []})  # pas de next_href

    ok, msg = _test_soundcloud({"user_id": "377065610", "client_id": "cid",
                                "client_secret": "sec"})  # pragma: allowlist secret

    assert ok is False
    assert "aucun titre public" in msg.lower()
