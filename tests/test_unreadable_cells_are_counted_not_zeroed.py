"""R502 — an unreadable cell is set aside and counted, never read 0 in silence.

Type: Feature
Uses: hypothesis, src/transformers/{csv_dialect,s4a_csv_parser,distrokid_parser}.py,
      src/dashboard/views/upload_csv.py (AST), src/dashboard/utils/csv_rejects.py
Depends on: nothing — pure functions, no DB, no Streamlit

Dead-letter queue (Reis & Housley, *Fundamentals of Data Engineering*, p.363): what
cannot be ingested is set aside without blocking the rest. Before R502, « 12x » in a
streams column read 0 and the file imported; a whole column of « n.c. » imported as
zeros. Now: counted per column, shown, logged in `csv_upload_log.rejected`, and the
file is refused by name past 5 % of a column (≥ 3 rejects) or at 100 %.
"""
import ast
import json
import pathlib

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.transformers.csv_dialect import (
    REJECT_FLOOR, ROW, ParsedRows, Rejects, UnreadableColumnError, finish)
from src.transformers.s4a_csv_parser import S4ACSVParser

_DETERMINISTIC = settings(derandomize=True, database=None, deadline=None,
                          max_examples=200)
_VIEW = pathlib.Path("src/dashboard/views/upload_csv.py")


def _timeline(streams, dates=None) -> pd.DataFrame:
    dates = dates or [f"2026-01-{i % 28 + 1:02d}" for i in range(len(streams))]
    df = pd.DataFrame({"date": dates, "streams": streams}, dtype=object)
    df.attrs["decimal"] = "."
    return df


def _parse(df):
    return S4ACSVParser().parse_timeline(df, artist_id=1, song_name="T")


_CELL = st.one_of(st.integers(0, 10**6).map(str), st.just(""),
                  st.sampled_from(["12x", "n.c.", "abc"]))


@_DETERMINISTIC
@given(cells=st.lists(_CELL, min_size=1, max_size=40),
       bad_dates=st.sets(st.integers(0, 39), max_size=3))
def test_every_row_in_is_a_row_out_or_a_counted_reject(cells, bad_dates):
    dates = [("pas une date" if i in bad_dates else f"2026-01-{i % 28 + 1:02d}")
             for i in range(len(cells))]
    try:
        rows = _parse(_timeline(cells, dates))
    except UnreadableColumnError as exc:
        assert exc.rejects.total >= 1
        return
    assert isinstance(rows, ParsedRows)
    dropped = len(rows.rejects.bad.get(ROW, []))
    assert len(rows) + dropped == len(cells), "a row vanished without being counted"
    unreadable = sum(c in ("12x", "n.c.", "abc") for c in cells)
    assert len(rows.rejects.bad.get("streams", [])) == unreadable


def test_two_bad_cells_in_twenty_import_and_are_counted():
    rows = _parse(_timeline(["10"] * 18 + ["12x", "n.c."]))
    assert len(rows) == 20 and rows.rejects.total == 2
    assert rows.rejects.describe() == "streams (2)"


def test_three_bad_cells_in_twenty_refuse_the_file_by_name():
    assert REJECT_FLOOR == 3
    with pytest.raises(UnreadableColumnError, match="streams"):
        _parse(_timeline(["10"] * 17 + ["12x"] * 3))


def test_a_column_entirely_unreadable_is_refused_even_when_short():
    with pytest.raises(UnreadableColumnError, match="streams"):
        _parse(_timeline(["n.c."]))


def test_a_french_export_with_a_thin_space_is_read_not_rejected():
    df = _timeline(["1 234", "1\xa0234", "1 234"])
    df.attrs["decimal"] = ","
    rows = _parse(df)
    assert [r["streams"] for r in rows] == [1234] * 3 and rows.rejects.total == 0


def test_a_blank_cell_is_not_a_reject():
    rows = _parse(_timeline(["", "-", "5"]))
    assert rows.rejects.total == 0


def test_the_logged_payload_is_bounded_and_serialisable():
    rejects = Rejects()
    for i in range(10):
        rejects.read("streams", i, "x" * 100, ".")
    payload = rejects.as_json()
    assert payload["streams"]["count"] == 10
    assert len(payload["streams"]["samples"]) == 3
    assert all(len(s) <= 40 for s in payload["streams"]["samples"])
    json.dumps(payload)
    assert Rejects().as_json() is None


def test_parsed_rows_stay_a_plain_list_to_their_callers():
    rows = finish([{"a": 1}], Rejects(), 1)
    assert rows == [{"a": 1}] and isinstance(rows, list)


def test_the_upload_guard_reads_a_french_column_and_refuses_an_unreadable_one():
    from src.dashboard.utils.csv_rejects import readable_numbers
    fr = pd.DataFrame({"listeners": ["1 234", "0"], "saves": ["0", "0"]})
    assert readable_numbers(fr, ("listeners", "saves"), ",")["listeners"].tolist() \
        == [1234, 0], "« 1 234 » read 0 made a real export look all-zero"
    junk = pd.DataFrame({"listeners": ["n.c.", "n.c."], "saves": ["0", "0"]})
    assert readable_numbers(junk, ("listeners", "saves"), ".") is None


def _log_insert_sql() -> list[str]:
    out = []
    for node in ast.walk(ast.parse(_VIEW.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and node.args:
            try:
                sql = ast.literal_eval(node.args[0])
            except (ValueError, SyntaxError, TypeError):
                continue
            if isinstance(sql, str) and "INSERT" in sql and "csv_upload_log" in sql:
                out.append(sql)
    return out


@pytest.mark.parametrize("status", ["rejected", "success", "error"])
def test_every_csv_log_insert_carries_the_rejects(status):
    matching = [s for s in _log_insert_sql() if f"'{status}'" in s]
    assert matching, f"no csv_upload_log insert of status {status!r} — repoint the guard"
    assert all("rejected" in s.split("VALUES")[0] for s in matching), (
        f"the `{status}` insert does not log what the parse set aside")
