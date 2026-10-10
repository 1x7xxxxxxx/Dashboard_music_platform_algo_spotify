"""R499 — the pure parsers hold a PROPERTY over their whole input space, not one example.

Type: Feature
Uses: hypothesis, src/transformers/{s4a_csv_parser,sacem_parser,csv_dialect}.py
Depends on: nothing — pure functions, no DB, no file

An example-based guard covers the case someone imagined. A property states what must
hold for EVERY input of a shape, and Hypothesis searches that shape and shrinks a
failure to its minimal case. The pilot targets the three number/separator readers an
artist's export goes through first (R52 is the locale-dependent precedent: a French
Excel writes `;` and groups thousands with a no-break space).

The profile is deterministic (`derandomize=True`, no example database): CI and a local
run explore the same inputs, so a red is reproducible and never flaky.
"""
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
from src.transformers.csv_dialect import SEPARATORS, sniff_separator
from src.transformers.distrokid_parser import DistroKidParser
from src.transformers.imusician_csv_parser import IMusicianCSVParser
from src.transformers.s4a_csv_parser import _to_int
from src.transformers.sacem_parser import _to_float

_DETERMINISTIC = settings(derandomize=True, database=None, deadline=None,
                          max_examples=300)

# Thousands separators a real export carries: US (`,`), none, and the three spaces a
# French locale writes — plain, no-break (U+00A0) and narrow no-break (U+202F).
_THOUSANDS_US = st.sampled_from([",", "", " ", "\u00a0", "\u202f"])
_THOUSANDS_FR = st.sampled_from(["", " ", "\u00a0", "\u202f"])


def _grouped(n: int, sep: str) -> str:
    return f"{n:,}".replace(",", sep)


# The four export parsers' count readers, with the thousands separators each accepts:
# S4A and Apple read `,` as grouping; DistroKid and iMusician read it as a decimal comma.
_COUNT_READERS = st.sampled_from([
    ("s4a", _to_int, _THOUSANDS_US),
    ("apple", lambda v: AppleMusicCSVParser.clean_number(None, v), _THOUSANDS_US),
    ("distrokid", lambda v: DistroKidParser._clean_numeric(v, int), _THOUSANDS_FR),
    ("imusician", lambda v: IMusicianCSVParser._clean_numeric(v, int), _THOUSANDS_FR),
])


@_DETERMINISTIC
@given(n=st.integers(min_value=0, max_value=10**10), reader=_COUNT_READERS,
       data=st.data())
def test_a_stream_count_reads_back_whatever_its_thousands_separator(n, reader, data):
    """R499 — found red on all four: `1\u00a0000` read as 0 (a French-locale export)."""
    _, lire, separateurs = reader
    assert lire(_grouped(n, data.draw(separateurs))) == n


@_DETERMINISTIC
@given(cents=st.integers(min_value=-10**9, max_value=10**9), sep=_THOUSANDS_FR)
def test_a_french_amount_reads_back_to_the_cent(cents, sep):
    euros = Decimal(cents) / 100
    entier, decimales = f"{abs(euros):.2f}".split(".")
    texte = ("-" if cents < 0 else "") + _grouped(int(entier), sep) + "," + decimales
    assert round(_to_float(texte), 2) == float(euros)


_FIELD = st.text(
    alphabet=st.characters(blacklist_characters="".join(SEPARATORS) + "\r\n﻿",
                           blacklist_categories=("Cs",)),
    min_size=1, max_size=12)


@_DETERMINISTIC
@given(fields=st.lists(_FIELD, min_size=2, max_size=8), sep=st.sampled_from(SEPARATORS),
       body=st.text(max_size=40))
def test_the_header_line_alone_names_the_separator(fields, sep, body):
    """Whatever the rows below hold — commas in a title included."""
    assert sniff_separator(sep.join(fields) + "\n" + body) == sep
