"""A caller must not be able to crash an endpoint with a byte.

Installed 2026-08-22 (R22, the fuzzing third). Found by `schemathesis` against a local
instance — 596 generated cases, one real server error:

    GET /streams/timeline?song=a%00b
    → ValueError: A string literal cannot contain NUL (0x00) characters
    → 500, uncaught, from src/database/postgres_handler.py:242

Any authenticated caller could crash that endpoint at will. It is not a data leak and
it is not remote code execution; it is a 500 that no test in the repo could produce,
because every test that exercises the endpoint passes a plausible song name.

That is the general point of this file. The suite tests what the endpoint is FOR;
these tests give it what nobody would send on purpose. The cases below are the ones
fuzzing actually surfaced, plus their close relatives — kept as literals so a future
run does not have to rediscover them.
"""
import pytest

pytest.importorskip("fastapi", reason="dev extras not installed — run `make sync`")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.auth import create_access_token  # noqa: E402
from src.api.deps import get_db  # noqa: E402
from src.api.main import app  # noqa: E402


def _token() -> str:
    return create_access_token({"sub": "fuzzer", "role": "artist",
                                "artist_id": 1, "tv": 0})


@pytest.fixture
def client(monkeypatch):
    """A client whose auth probe succeeds, so requests reach the endpoint body.

    Without the override, R24's revocation check answers 401 for a username that is
    not in the database, and every assertion below would pass on a 401 — measuring
    nothing about hostile input.
    """
    from unittest.mock import MagicMock

    import pandas as pd

    db = MagicMock()
    db.fetch_query.return_value = [(True, 0, "artist", 1)]
    db.fetch_df.return_value = pd.DataFrame()
    db.close = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


# The bytes and strings that break something somewhere in the stack. `%00` is the one
# fuzzing actually found; the others are the same question asked of other layers.
HOSTILE = [
    pytest.param("a%00b", id="nul-byte"),
    pytest.param("%00", id="nul-alone"),
    pytest.param("a%00", id="nul-trailing"),
    pytest.param("%25%30%30", id="double-encoded-nul"),
    pytest.param("%ff%fe", id="invalid-utf8"),
    pytest.param("a" * 4000, id="very-long"),
    pytest.param("%27%20OR%201%3D1--", id="sql-ish"),
    pytest.param("%C3%A9%F0%9F%8E%B5", id="unicode-and-emoji"),
    pytest.param("%0A%0D", id="crlf"),
]


@pytest.mark.parametrize("value", HOSTILE)
def test_a_hostile_song_filter_never_500s(client, value):
    """Any answer but a 5xx. 400 and 422 are fine — a crash is not."""
    r = client.get(f"/streams/timeline?song={value}",
                   headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code < 500, (
        f"song={value!r} produced HTTP {r.status_code}. A caller who can choose a "
        f"query parameter can then stop the endpoint answering anyone.\n{r.text[:300]}"
    )


def test_the_nul_byte_is_refused_before_it_reaches_the_database(client):
    """Specifically 400, and specifically from the edge.

    Not merely "< 500": the reason this is a 400 rather than an empty 200 is that a
    NUL in a URL is a malformed request, and answering it normally would hide a
    client bug. The check lives in the middleware so every string parameter this API
    grows later inherits it without its author remembering.
    """
    r = client.get("/streams/timeline?song=a%00b",
                   headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 400, r.text
    assert "NUL" in r.text


def test_a_clean_request_still_works(client):
    """Non-vacuity: without this, refusing EVERYTHING would pass every test above."""
    r = client.get("/streams/timeline?song=abc",
                   headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 200, r.text


def test_the_health_probe_is_never_blocked_by_the_edge_check():
    """Infra probes must survive every guard added in front of the app."""
    assert TestClient(app).get("/health").status_code == 200


def test_the_stripe_webhook_body_is_not_consumed_by_the_edge_check(client):
    """The NUL check must not read the body — Stripe's signature covers exact bytes.

    A middleware that calls `await request.body()` leaves the downstream handler with
    an exhausted stream, or forces a re-buffer. The webhook answering 400 "invalid
    signature" (rather than hanging, or 500ing on an empty body) is the evidence it
    still received what was sent.
    """
    r = client.post("/webhooks/stripe", content=b'{"id":"evt_test"}',
                    headers={"stripe-signature": "t=1,v1=deadbeef"})
    assert r.status_code in (400, 503), r.text
    assert r.status_code < 500 or "signature" in r.text.lower()


# ── The half a mock cannot show ─────────────────────────────────────────────
# Everything above runs against a MagicMock database, so it proves the EDGE refuses
# the byte. It cannot prove why that matters: a MagicMock accepts a NUL happily, and
# `test_a_hostile_song_filter_never_500s[nul-byte]` therefore passed even with the
# middleware removed. Only `test_the_nul_byte_is_refused_before_it_reaches_the
# _database` went red on that mutation.
#
# This is the other end of the chain, against the real driver: the reason the edge
# check is not decoration.

def test_psycopg2_really_does_refuse_a_nul_and_that_is_why_the_edge_check_exists():
    from tests.db_gate import db_ready

    if not db_ready():
        pytest.skip("needs the live schema to exercise the real driver")

    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        with pytest.raises(ValueError, match="NUL"):
            db.fetch_df("SELECT %s::text AS v", ("a\x00b",))
    finally:
        db.close()
