"""Regression tests for CSV auto-detection + Spotify identity parsing.

Type: Utility
Guards the Benken onboarding incident (2026-06-19):
  - S4A / iMusician exports returned "type non reconnu" because detection required
    an exact filename token ('-timeline') + exact column names. Apple worked because
    it used flexible any()-of-aliases matching.
  - Spotify produced 0 rows for a new tenant because no per-tenant artist identity
    was captured.
"""
import pytest

from src.dashboard.views.upload_csv import _detect_platform
from src.dashboard.views.credentials._core import extract_spotify_artist_id


# ── CSV detection — the cases Benken's real exports hit ────────────────────────

@pytest.mark.parametrize("filename, columns, expected", [
    # S4A per-song timeline WITHOUT a '-timeline' filename token (the exact regression)
    ("spotify_export.csv", ["Date", "Streams"], "s4a"),
    ("Streams.csv", ["Date", "Écoutes"], "s4a"),
    # S4A audience detected by columns even without 'audience' in the filename
    ("export.csv", ["Date", "Listeners", "Streams"], "s4a_audience"),
    # S4A songs-all by columns (song + release_date/saves), no filename token
    ("catalogue.csv", ["Song", "Release_date", "Saves", "Streams"], "s4a_songs_global"),
    # iMusician summary detected via 'total revenue' (parser-aligned), not only 'track streams'
    ("rapport.csv", ["Statement date", "Release title", "Total revenue"], "imusician_summary"),
    ("rapport.csv", ["Release title", "Track streams"], "imusician_summary"),
    # iMusician sales (ISRC + shop) — unchanged, still specific
    ("ventes.csv", ["ISRC", "Shop", "Revenue"], "imusician_sales"),
    # Apple — unchanged (already worked for Benken)
    ("apple.csv", ["Morceau", "Écoutes"], "apple"),
    # DistroKid — unchanged specific signature
    ("dk.csv", ["Sale Month", "Earnings (USD)"], "distrokid_sales"),
])
def test_detect_platform_known(filename, columns, expected):
    assert _detect_platform(filename, columns) == expected


def test_detect_platform_unknown_returns_none():
    assert _detect_platform("mystery.csv", ["foo", "bar", "baz"]) is None


def test_detect_platform_is_case_insensitive():
    # Headers come in any case from real exports; detection lowercases + strips.
    assert _detect_platform("x.csv", ["  DATE ", "STREAMS"]) == "s4a"


# ── Spotify identity parsing — URL / URI / bare ID all normalise to the bare ID ─

_SPOTIFY_ID = "3TVXtAsR1Inumwj472S9r4"


@pytest.mark.parametrize("value", [
    _SPOTIFY_ID,
    f"https://open.spotify.com/artist/{_SPOTIFY_ID}",
    f"https://open.spotify.com/artist/{_SPOTIFY_ID}?si=abcdef",
    f"spotify:artist:{_SPOTIFY_ID}",
    f"  {_SPOTIFY_ID}  ",
])
def test_extract_spotify_artist_id(value):
    assert extract_spotify_artist_id(value) == _SPOTIFY_ID


def test_extract_spotify_artist_id_empty():
    assert extract_spotify_artist_id("") == ""
    assert extract_spotify_artist_id(None) == ""
