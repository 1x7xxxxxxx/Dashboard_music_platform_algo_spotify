"""A partial date from an API must never reach a DATE column raw.

Measured 2026-08-21: Spotify returns `album.release_date` at year, month or day
precision. `tracks.release_date` is DATE, so "2013" raised
`invalid input syntax for type date: "2013"` and — the write being batched per
artist — cost that artist EVERY top track of the run.

It had never fired in ~2 years because the admin's own catalogue carries full dates.
Only the canary, a second tenant pointing at a different catalogue, could surface it.

Error class: api-partial-date-into-date-column (.claude/dev-docs/error-classes.md).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src.utils.api_dates import coerce_api_date

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2013-05-21", dt.date(2013, 5, 21)),   # day precision
        ("2013-05", dt.date(2013, 5, 1)),       # month precision -> first of month
        ("2013", dt.date(2013, 1, 1)),          # year precision  -> first of year
        (dt.date(2013, 5, 21), dt.date(2013, 5, 21)),
        (dt.datetime(2013, 5, 21, 12, 0), dt.date(2013, 5, 21)),
    ],
)
def test_every_precision_spotify_declares_becomes_a_date(raw, expected) -> None:
    assert coerce_api_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "not-a-date", "2013-13-45", 0])
def test_an_unusable_value_becomes_none_not_an_exception(raw) -> None:
    """A malformed date must cost one column, never the artist's whole batch."""
    assert coerce_api_date(raw) is None


def test_padding_goes_to_the_start_of_the_period_never_to_today() -> None:
    """An unknown day must not read as 'released this month' in recency features."""
    got = coerce_api_date("2013")
    assert (got.month, got.day) == (1, 1)
    assert got != dt.date.today()


def test_the_spotify_collector_coerces_before_writing() -> None:
    """The site that failed. A raw dict lookup here is the defect itself."""
    text = (ROOT / "src/collectors/spotify_api.py").read_text(encoding="utf-8")
    assert "coerce_api_date(track['album']" in text, (
        "spotify_api.py assigns release_date without coercing it — a year-precision "
        "album will abort the artist's entire upsert batch again."
    )
    assert "release_date = track['album']['release_date']" not in text, (
        "the raw assignment is back; it is what raised "
        'invalid input syntax for type date: "2013"'
    )


def test_the_collected_payload_survives_a_year_only_album() -> None:
    """End to end on the shape the API really returns, without touching the network."""
    pytest.importorskip("spotipy", reason="collector dependency; present in the containers")
    from src.collectors.spotify_api import SpotifyCollector

    album = {"name": "Discovery", "release_date": "2001", "release_date_precision": "year"}
    track = {"id": "t1", "name": "One More Time", "popularity": 85,
             "duration_ms": 320357, "explicit": False, "album": album}

    class _FakeSp:
        def artist_top_tracks(self, artist_id, country="FR"):
            return {"tracks": [track]}

    c = SpotifyCollector.__new__(SpotifyCollector)
    c.sp = _FakeSp()
    rows = c.get_artist_top_tracks("4tZwfgrHOc3mvqYlEYSvVi")
    assert len(rows) == 1
    assert rows[0]["release_date"] == dt.date(2001, 1, 1), (
        f"the collector still hands a partial date to psycopg2: "
        f"{rows[0]['release_date']!r}"
    )


# ── Meta token shape ─────────────────────────────────────────────────────────
# Different API, same family of defect: a value that LOOKS present and is subtly
# wrong, whose error message points at the wrong cause.

def test_the_exact_production_defect_is_caught() -> None:
    """`EEAA…` — one stray leading character, weeks of silent non-collection."""
    from src.utils.meta_token_format import token_format_problem

    problem = token_format_problem("E" + "EAA" + "x" * 100)
    assert problem and "extra character" in problem, problem


def test_a_well_formed_token_is_not_rejected() -> None:
    from src.utils.meta_token_format import token_format_problem

    assert token_format_problem("EAA" + "x" * 150) is None


def test_absence_is_not_reported_as_a_format_problem() -> None:
    """Missing is a different failure, reported by a different check."""
    from src.utils.meta_token_format import token_format_problem

    assert token_format_problem(None) is None
    assert token_format_problem("") is None


def test_quotes_and_whitespace_are_named_precisely() -> None:
    from src.utils.meta_token_format import token_format_problem

    assert "quotes" in (token_format_problem('"EAA' + "x" * 150 + '"') or "")
    assert "whitespace" in (token_format_problem(" EAA" + "x" * 150) or "")
