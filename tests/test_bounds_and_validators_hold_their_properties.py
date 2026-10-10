"""R504 — a window never ends before it starts; a validator only ever raises its own error.

Type: Feature
Uses: hypothesis, src/dashboard/utils/{entry_period,app_settings}.py,
      src/database/postgres_handler.py
Depends on: nothing — pure functions, no DB, no Streamlit

Each property was red before R504: a release set in the future gave a post-release
window ending 10 days before its start; `valider_montant("²")` raised a raw
`ValueError` and accepted `"١٢٣"`; `validate_columns` let anything starting with `(`
through, and its `$` accepted a trailing newline.
"""
import datetime as dt

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.dashboard.utils.app_settings import ReglageInvalide, valider_montant
from src.dashboard.utils.entry_period import POST_RELEASE, PRESETS, resolve
from src.database.postgres_handler import (
    validate_columns,
    validate_conflict_expression,
)

_DETERMINISTIC = settings(derandomize=True, database=None, deadline=None,
                          max_examples=300)
_DAYS = st.dates(min_value=dt.date(2020, 1, 1), max_value=dt.date(2030, 12, 31))


@_DETERMINISTIC
@given(preset=st.sampled_from(sorted({**PRESETS, **POST_RELEASE})), today=_DAYS,
       release=st.none() | _DAYS, custom=st.none() | st.tuples(_DAYS, _DAYS))
def test_a_window_never_ends_before_it_starts_nor_after_today(preset, today, release,
                                                               custom):
    w = resolve(preset, today, release=release, custom=custom)
    assert w.start <= w.end
    if preset != "custom":
        assert w.end <= today, "a window that ends tomorrow describes a figure not yet born"


@_DETERMINISTIC
@given(st.text(max_size=12))
def test_an_amount_validator_only_ever_raises_its_own_error(valeur):
    try:
        rendu = valider_montant(valeur)
    except ReglageInvalide:
        return
    assert rendu == "" or (rendu.isascii() and rendu.isdigit() and int(rendu) > 0)


@pytest.mark.parametrize("texte", ["1 200", "1 200 €", "1 200€"])
def test_an_amount_written_with_a_french_space_is_read(texte):
    assert valider_montant(texte) == "1200"


@pytest.mark.parametrize("texte", ["²", "١٢٣", "4²"])
def test_a_digit_that_is_not_ascii_is_refused_by_name(texte):
    """`str.isdigit` accepts both; `int("²")` then raised a bare ValueError."""
    with pytest.raises(ReglageInvalide):
        valider_montant(texte)


@_DETERMINISTIC
@given(st.text(max_size=20))
def test_a_column_name_passes_only_as_a_whole_identifier(col):
    import re
    try:
        validate_columns([col])
    except ValueError:
        assert not re.fullmatch(r"[a-z_][a-z0-9_]*", col)
        return
    assert re.fullmatch(r"[a-z_][a-z0-9_]*", col)


@pytest.mark.parametrize("col", ["abc\n", "(x); DROP TABLE t; --", "(collected_at::date)"])
def test_a_column_name_never_passes_with_a_newline_or_a_parenthesis(col):
    with pytest.raises(ValueError):
        validate_columns([col])


def test_a_conflict_expression_is_a_cast_of_one_identifier():
    validate_conflict_expression("(collected_at::date)")
    for bad in ["(x); DROP TABLE t; --", "(collected_at::date)\n", "(a::date, b)", "(A::date)"]:
        with pytest.raises(ValueError):
            validate_conflict_expression(bad)
