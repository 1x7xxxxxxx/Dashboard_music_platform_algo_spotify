"""R503 — the decimal mark of a number is decided once per FILE, by one reader.

Type: Feature
Uses: hypothesis, src/transformers/csv_dialect.py, src/dashboard/utils/formats.py,
      src/transformers/{s4a_csv_parser,apple_music_csv_parser,distrokid_parser,
      imusician_csv_parser,sacem_parser}.py
Depends on: nothing — pure functions, no DB

Before R503, `1.234,5` read 1 (S4A), 0 (Apple), 0.0 (DistroKid, iMusician) — five
readers, five answers. The property is a round trip: what our own formatter writes in a
locale, the reader reads back in that locale's decimal mark.
"""
import io

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.dashboard.utils.formats import num
from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
from src.transformers.csv_dialect import decimal_for, read_number
from src.transformers.distrokid_parser import DistroKidParser
from src.transformers.imusician_csv_parser import IMusicianCSVParser
from src.transformers.s4a_csv_parser import _to_int
from src.transformers.sacem_parser import _to_float

_DETERMINISTIC = settings(derandomize=True, database=None, deadline=None,
                          max_examples=300)
_DECIMAL_OF = {"fr": ",", "en": "."}


@_DETERMINISTIC
@given(cents=st.integers(min_value=-10**12, max_value=10**12),
       lang=st.sampled_from(sorted(_DECIMAL_OF)), digits=st.sampled_from([0, 1, 2]))
def test_what_the_formatter_writes_the_reader_reads_back(cents, lang, digits):
    x = round(cents / 100, digits)
    assert read_number(num(x, digits, lang=lang), _DECIMAL_OF[lang]) == pytest.approx(x)


@pytest.mark.parametrize("text", ["abc", "1.2.3", "12,34,5", "1..2", "+", "1 2x"])
def test_an_unreadable_number_raises_instead_of_reading_zero(text):
    with pytest.raises(ValueError):
        read_number(text, ".")


@pytest.mark.parametrize("text", ["", "-", "—", "nan", None, float("nan")])
def test_a_blank_cell_is_none_not_a_rejection(text):
    assert read_number(text, ",") is None


def test_a_semicolon_file_is_a_decimal_comma_file():
    assert decimal_for(";") == ","
    assert {decimal_for(s) for s in (",", "\t", "|")} == {"."}


_READERS = [
    ("s4a", lambda v, d: _to_int(v, decimal=d)),
    ("apple", lambda v, d: AppleMusicCSVParser.clean_number(None, v, d)),
    ("distrokid", lambda v, d: DistroKidParser._clean_numeric(v, int, decimal=d)),
    ("imusician", lambda v, d: IMusicianCSVParser._clean_numeric(v, int, decimal=d)),
]


@pytest.mark.parametrize("name,lire", _READERS, ids=[r[0] for r in _READERS])
def test_every_reader_gives_the_same_answer_to_a_european_number(name, lire):
    """Red before R503: 1, 0, 0 and 0."""
    assert lire("1.234,5", ",") == 1234
    assert lire("1.234", ",") == 1234
    assert lire("1,234", ".") == 1234


def test_a_sacem_amount_is_read_in_french():
    assert _to_float("1.234,56") == pytest.approx(1234.56)


def test_a_semicolon_distrokid_export_reads_its_european_amounts():
    raw = ("Reporting Date;Sale Month;Store;Artist;Title;ISRC;Quantity;Earnings (USD)\n"
           "2026-01-05;2025-12;Spotify;A;T;XX1;1.234;1.234,56\n").encode()
    rows = DistroKidParser().parse_upload(io.BytesIO(raw), artist_id=1)
    assert rows[0]["quantity"] == 1234
    assert rows[0]["earnings_usd"] == pytest.approx(1234.56)
