"""
Guard — a YouTube channel with no uploads yields 0 videos, it does not raise.

Type: Sub
Uses: src.utils.api_errors.is_empty_uploads_playlist, src.utils.safe_error
Triggers: pytest
Depends on: nothing at runtime (no network, no DB, no vendor SDK — see api_errors)
Persists in: nothing

Error class: decision-made-on-a-string-truncated-for-display.

Measured in production 2026-08-23. The empty-channel branch existed and was
unreachable: it tested `'playlistNotFound' in safe_error(he)`, and `safe_error()`
truncates at 300 characters for LOG HYGIENE while the token sits at index 455 of a
real 531-character googleapiclient repr. So every night `youtube_daily` retried 3x
and raised for tenant 12, whose channel simply has no videos — and the channel
snapshot it had already fetched was lost with the exception. The DAG stayed SUCCESS,
the tenant's status went `stale`, and `readiness_red_flags` excludes `stale`.

The first test is the one that matters: it pins the PROPERTY that killed the old
test, so nobody can reintroduce a substring test against a truncated string.
"""

import pytest

from src.utils.api_errors import is_empty_uploads_playlist
from src.utils.safe_error import safe_error

# The exact SHAPE googleapiclient produces, transcribed from the production log —
# with the key replaced by a fake one. The real key was in this fixture for about
# twenty minutes: writing a guard against secrets in logs, I pasted a log line
# containing the secret. The shape is what the test needs; the value never was.
# Length matters (it pushes `playlistNotFound` past the 300-char truncation), the
# characters do not.
_PROD_REPR = (
    '<HttpError 404 when requesting https://youtube.googleapis.com/youtube/v3/'
    'playlistItems?part=snippet%2CcontentDetails&playlistId=UUhildcM-pMjEKMtg77A-hlg'
    '&maxResults=50&key=AIzaSyFAKE_KEY_FOR_THE_FIXTURE_ONLY&alt=json returned '
    '"The playlist identified with the request\'s <code>playlistId</code> parameter '
    'cannot be found.". Details: "[{\'message\': "The playlist identified with the '
    'request\'s <code>playlistId</code> parameter cannot be found.", \'domain\': '
    '\'youtube.playlistItem\', \'reason\': \'playlistNotFound\', \'location\': '
    '\'playlistId\', \'locationType\': \'parameter\'}]">'
)

_EMPTY_UPLOADS_DETAILS = [{
    'message': "The playlist identified with the request's playlistId parameter cannot be found.",
    'domain': 'youtube.playlistItem',
    'reason': 'playlistNotFound',
    'location': 'playlistId',
    'locationType': 'parameter',
}]


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeHttpError(Exception):
    def __init__(self, status: int, error_details, text: str = _PROD_REPR) -> None:
        super().__init__(text)
        self.resp = _Resp(status)
        self.error_details = error_details
        self._text = text

    def __str__(self) -> str:
        return self._text


def test_the_reason_is_past_the_truncation_limit() -> None:
    """The premise of this whole guard: a substring test CANNOT see the reason."""
    err = _FakeHttpError(404, _EMPTY_UPLOADS_DETAILS)
    assert 'playlistNotFound' not in safe_error(err), (
        "safe_error() no longer truncates the reason away. If its limit changed, the "
        "old substring test would start passing by luck — decide deliberately rather "
        "than deleting this test."
    )
    assert is_empty_uploads_playlist(err), (
        "the structural read must succeed on exactly the payload the string read misses"
    )


def test_empty_uploads_playlist_is_recognised() -> None:
    assert is_empty_uploads_playlist(_FakeHttpError(404, _EMPTY_UPLOADS_DETAILS))


@pytest.mark.parametrize("status, details, why", [
    (404, [{'reason': 'channelNotFound'}], "a missing CHANNEL is a real error"),
    (403, _EMPTY_UPLOADS_DETAILS, "a quota/permission failure is a real error"),
    (500, [], "a server error is a real error"),
    (404, [], "a 404 with no structured reason is not proof of an empty channel"),
    (404, "", "error_details defaults to a str — iterating it must not match"),
    (404, None, "a missing attribute is not proof of an empty channel"),
])
def test_everything_else_still_raises(status, details, why) -> None:
    assert not is_empty_uploads_playlist(_FakeHttpError(status, details)), why


def test_an_object_without_resp_is_not_an_empty_channel() -> None:
    assert not is_empty_uploads_playlist(ValueError("nothing to do with HTTP"))
