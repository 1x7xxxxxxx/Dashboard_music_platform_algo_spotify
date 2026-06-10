"""Regression guard for the song-name representation mismatch (?/_ etc.).

s4a_song_timeline / ml_song_predictions are filename-derived ('_'), while CSV/API
tables keep the real chars. canonical_song() bridges the two for exact joins.
This pins the contract so the fix can't silently regress.
"""
import pandas as pd

from src.transformers.s4a_csv_parser import S4ACSVParser
from src.utils.track_matching import canonical_song, canonical_song_sql


def test_canonical_song_replaces_all_fs_invalid_chars():
    assert canonical_song("Qui a bu le crachoir du saloon ?") == "Qui a bu le crachoir du saloon _"
    assert canonical_song("AC/DC") == "AC_DC"
    assert canonical_song('a:b"c<d>e|f*g') == "a_b_c_d_e_f_g"


def test_canonical_song_preserves_accents_and_remix():
    # Must NOT collapse like normalize_track_title — distinct tracks stay distinct.
    assert canonical_song("Kimono à semelle de fer - Remix") == "Kimono à semelle de fer - Remix"
    assert canonical_song("") == ""


def test_canonical_song_is_idempotent():
    once = canonical_song("Qui a bu le crachoir du saloon ?")
    assert canonical_song(once) == once


def test_canonical_song_sql_fragment_shape():
    frag = canonical_song_sql("track_name")
    assert frag.startswith("translate(track_name,")
    # one '_' in the replacement set per invalid char
    assert "'" + "_" * len('<>:"/\\|?*') + "'" in frag


def test_parse_songs_global_normalizes_song_names():
    df = pd.DataFrame({
        "song": ["Qui a bu le crachoir du saloon ?", "AC/DC"],
        "listeners": [10, 20], "streams": [100, 200], "saves": [1, 2],
        "release_date": ["2024-01-01", "2024-02-01"],
    })
    rows = S4ACSVParser().parse_songs_global(df, artist_id=1, filename="x-songs-1year.csv")
    names = {r["song"] for r in rows}
    assert names == {"Qui a bu le crachoir du saloon _", "AC_DC"}
    assert all("?" not in r["song"] and "/" not in r["song"] for r in rows)
