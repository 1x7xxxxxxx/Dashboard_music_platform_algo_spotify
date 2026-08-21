"""What an artist pastes into the Channel ID field, and what happens to it.

Installed 2026-08-21 (roadmap R14, the YouTube half).

The form asks for `UC…`. Nobody knows theirs. Benken pasted something else on
2026-06-19 and got « Channel ID introuvable » at the last step of the setup — a
dead end with no next move, and the reason that account collected nothing.

Two properties are pinned here, and the second matters more than the first:

  1. every shape a real artist has to hand is recognised — the handle under their
     name, the address bar in any of YouTube's four URL forms, and a raw id;
  2. a resolved id is REPORTED, never substituted. `_test_youtube` returns
     `False` with the id to paste, even when it found one. Silently adopting an
     identity the artist did not type is the exact mechanism this repo spent two
     sessions removing (`tenant-identity-falls-back-to-admin`) — and "helpfully"
     filling in a channel is how you collect someone else's catalogue.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.dashboard.utils.youtube_channel import (
    lookup_params,
    parse_channel_input,
    topic_channel_query,
)

# A real, well-formed id: UC + 22 chars. Google's own developer-docs channel.
GOOD_ID = "UC_x5XG1OV2P6uZZ5FSM9Ttw"


# ── The parser ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,kind,value",
    [
        (GOOD_ID, "id", GOOD_ID),
        (f"  {GOOD_ID}  ", "id", GOOD_ID),
        (f"https://www.youtube.com/channel/{GOOD_ID}", "id", GOOD_ID),
        (f"youtube.com/channel/{GOOD_ID}?view=0", "id", GOOD_ID),
        ("@benken", "handle", "@benken"),
        ("https://www.youtube.com/@benken", "handle", "@benken"),
        ("youtube.com/@benken/videos", "handle", "@benken"),
        ("https://youtube.com/user/benkenmusic", "user", "benkenmusic"),
        ("https://youtube.com/c/Benken", "name", "Benken"),
        ("UCtooshort", "malformed", "UCtooshort"),
        ("", "unknown", ""),
        (None, "unknown", ""),
        ("benken", "unknown", "benken"),
    ],
)
def test_every_shape_an_artist_has_to_hand(raw, kind, value):
    parsed = parse_channel_input(raw)
    assert (parsed.kind, parsed.value) == (kind, value)


def test_a_handle_url_is_not_read_as_a_vanity_name():
    """`/@name` and `/c/name` are different lookups — one resolves, one cannot."""
    assert parse_channel_input("youtube.com/@benken").kind == "handle"
    assert parse_channel_input("youtube.com/c/benken").kind == "name"


def test_only_a_real_id_is_usable_as_is():
    assert parse_channel_input(GOOD_ID).is_usable
    for other in ("@benken", "UCtooshort", "youtube.com/c/Benken", "benken"):
        assert not parse_channel_input(other).is_usable, other


def test_the_parser_and_the_lookup_cannot_drift():
    """Every kind the parser calls resolvable must have an API filter."""
    for raw in ("@benken", "https://youtube.com/user/benkenmusic"):
        parsed = parse_channel_input(raw)
        assert parsed.is_resolvable
        assert lookup_params(parsed), f"{parsed.kind} is resolvable but has no filter"
    for raw in (GOOD_ID, "youtube.com/c/Benken", "UCtooshort", "benken"):
        parsed = parse_channel_input(raw)
        assert not parsed.is_resolvable
        assert lookup_params(parsed) is None, f"{parsed.kind} got a filter it cannot use"


def test_topic_query_needs_a_name():
    assert topic_channel_query("Benken") == "Benken - Topic"
    assert topic_channel_query("  ") is None
    assert topic_channel_query(None) is None


# ── The connection test: report, never substitute ────────────────────────────

def _resp(status: int, payload: dict) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    return m


def _run(channel_value: str, channel_payload: dict):
    """Drive _test_youtube with a valid key and a controlled channels.list reply."""
    from src.dashboard.views.credentials import _platform_youtube as mod

    key_ok = _resp(200, {"items": [{"id": "fr"}]})

    def _get(url, **kwargs):
        return key_ok if "i18nLanguages" in url else _resp(200, channel_payload)

    with patch.object(mod.requests, "get", side_effect=_get):
        return mod._test_youtube({"api_key": "AIzaKey",  # pragma: allowlist secret
                                  "channel_id": channel_value})


def test_a_handle_is_resolved_and_the_id_is_handed_back():
    ok, msg = _run("@benken", {"items": [{"id": GOOD_ID}]})
    assert ok is False, (
        "the test went green on a handle. Resolution must be reported so the "
        "artist puts the id in themselves — never adopted on their behalf."
    )
    assert GOOD_ID in msg, f"the resolved id is not in the message: {msg!r}"


def test_an_unknown_handle_says_so_instead_of_dead_ending():
    ok, msg = _run("@nobody-here", {"items": []})
    assert ok is False
    assert "nobody-here" in msg


def test_a_truncated_id_is_named_as_truncated():
    """`UCabc` used to 404 as 'introuvable', which sends the artist looking again."""
    ok, msg = _run("UCtooshort", {"items": []})
    assert ok is False
    assert "24" in msg or "tronqué" in msg.lower()


def test_a_vanity_url_says_it_cannot_be_resolved():
    ok, msg = _run("youtube.com/c/Benken", {"items": []})
    assert ok is False
    assert "Studio" in msg


def test_a_real_id_still_goes_through_to_the_channel_check():
    """The happy path must not be broken by any of the above."""
    ok, msg = _run(GOOD_ID, {"items": [{"statistics": {"videoCount": "42"}}]})
    assert ok is True, msg
    assert "42" in msg
