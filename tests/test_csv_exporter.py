"""Unit tests for src/dashboard/utils/csv_exporter.py."""
import io
import zipfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.dashboard.utils.csv_exporter import export_all, table_names, _TABLES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(df_per_table: dict | None = None, default_df: pd.DataFrame | None = None):
    """Return a mock PostgresHandler whose fetch_df returns controlled DataFrames."""
    db = MagicMock()
    if df_per_table is None:
        df_per_table = {}

    def _fetch_df(sql, params=None):
        for table_name, ret_df in df_per_table.items():
            if table_name in sql:
                return ret_df
        return default_df if default_df is not None else pd.DataFrame()

    db.fetch_df.side_effect = _fetch_df
    return db


def _open_zip(buf: io.BytesIO) -> zipfile.ZipFile:
    buf.seek(0)
    return zipfile.ZipFile(buf)


# ---------------------------------------------------------------------------
# table_names()
# ---------------------------------------------------------------------------

def test_table_names_returns_list_of_strings():
    names = table_names()
    assert isinstance(names, list)
    assert len(names) > 0
    assert all(isinstance(n, str) for n in names)


def test_table_names_matches_tables_constant():
    assert table_names() == [t for t, _, _ in _TABLES]


# ---------------------------------------------------------------------------
# export_all — full export
# ---------------------------------------------------------------------------

def test_export_all_returns_bytes_io():
    db = _make_db()
    result = export_all(db, artist_id=1)
    assert isinstance(result, io.BytesIO)


def test_export_all_zip_contains_index():
    db = _make_db()
    with _open_zip(export_all(db, artist_id=1)) as zf:
        assert "_index.txt" in zf.namelist()


def test_export_all_zip_contains_csv_for_every_table():
    db = _make_db()
    with _open_zip(export_all(db, artist_id=1)) as zf:
        names = zf.namelist()
    for tbl in table_names():
        assert f"{tbl}.csv" in names, f"Missing {tbl}.csv in ZIP"


def test_export_all_csv_has_correct_data():
    sample = pd.DataFrame({"song": ["Track A", "Track B"], "streams": [100, 200]})
    db = _make_db(df_per_table={"s4a_song_timeline": sample})

    with _open_zip(export_all(db, artist_id=1)) as zf:
        raw = zf.read("s4a_song_timeline.csv").decode("utf-8")

    df_out = pd.read_csv(io.StringIO(raw))
    assert list(df_out.columns) == ["song", "streams"]
    assert len(df_out) == 2
    assert df_out["song"].tolist() == ["Track A", "Track B"]


def test_export_all_index_contains_artist_id():
    db = _make_db()
    with _open_zip(export_all(db, artist_id=42)) as zf:
        index_text = zf.read("_index.txt").decode("utf-8")
    assert "artist_id = 42" in index_text


def test_export_all_index_lists_tables_with_data():
    sample = pd.DataFrame({"col": [1, 2]})
    db = _make_db(default_df=sample)
    with _open_zip(export_all(db, artist_id=1)) as zf:
        index_text = zf.read("_index.txt").decode("utf-8")
    assert "Tables avec données" in index_text


def test_export_all_handles_fetch_error_gracefully():
    """A table that raises an exception should be skipped, not crash the export."""
    db = MagicMock()
    db.fetch_df.side_effect = Exception("DB error")
    result = export_all(db, artist_id=1)
    with _open_zip(result) as zf:
        assert "_index.txt" in zf.namelist()


# ---------------------------------------------------------------------------
# export_all — table selection
# ---------------------------------------------------------------------------

def test_export_with_table_subset_only_includes_selected():
    subset = ["s4a_song_timeline", "youtube_channels"]
    db = _make_db()
    with _open_zip(export_all(db, artist_id=1, tables=subset)) as zf:
        csv_files = [n for n in zf.namelist() if n.endswith(".csv")]
    assert set(csv_files) == {"s4a_song_timeline.csv", "youtube_channels.csv"}


def test_export_with_empty_table_list_produces_index_only():
    db = _make_db()
    with _open_zip(export_all(db, artist_id=1, tables=[])) as zf:
        assert zf.namelist() == ["_index.txt"]


def test_export_tables_none_exports_all():
    db = _make_db()
    with _open_zip(export_all(db, artist_id=1, tables=None)) as zf:
        csv_files = {n for n in zf.namelist() if n.endswith(".csv")}
    assert csv_files == {f"{t}.csv" for t in table_names()}


def test_export_artist_id_passed_to_params_builder():
    """fetch_df must be called with the correct artist_id in params."""
    db = _make_db()
    export_all(db, artist_id=99, tables=["s4a_song_timeline"])
    # Every call to fetch_df for s4a_song_timeline should include 99 in params
    calls = [
        call for call in db.fetch_df.call_args_list
        if "s4a_song_timeline" in call.args[0]
    ]
    assert len(calls) == 1
    assert 99 in calls[0].args[1]  # params tuple
