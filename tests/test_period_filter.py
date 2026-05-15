"""Unit tests for src/dashboard/utils/period_filter.py (pure functions only)."""
import datetime as dt

import pytest
from src.dashboard.utils.period_filter import (
    PeriodWindow,
    _default_preset,
    _resolve_window,
    _validate,
)

_TODAY = dt.date(2026, 5, 15)            # a Friday
_MIN = dt.date(2025, 1, 1)
_MAX = dt.date(2026, 5, 10)


# ── _default_preset: data-span heuristic ──────────────────────────────────
def test_default_preset_short_span_is_month():
    assert _default_preset(90, None) == ("current", "month")


def test_default_preset_boundary_91_is_year():
    assert _default_preset(91, None) == ("current", "year")


def test_default_preset_no_span_defaults_year():
    assert _default_preset(None, None) == ("current", "year")


def test_default_preset_override_wins():
    assert _default_preset(10, "all") == ("all", "year")


def test_default_preset_unknown_override_ignored():
    assert _default_preset(10, "bogus") == ("current", "month")


# ── _resolve_window: every preset ─────────────────────────────────────────
def test_resolve_all_history_flag_and_bounds():
    w = _resolve_window("all", "month", _TODAY, _MIN, _MAX, None, None)
    assert w.is_all_history is True
    assert (w.start, w.end) == (_MIN, _MAX)
    assert w.sql_between("date") == ("", ())


def test_resolve_custom_range():
    rng = (dt.date(2026, 2, 1), dt.date(2026, 3, 1))
    w = _resolve_window("custom", "month", _TODAY, _MIN, _MAX, None, rng)
    assert (w.start, w.end) == rng
    assert w.is_all_history is False


def test_resolve_last_release_with_date():
    rel = dt.date(2026, 4, 20)
    w = _resolve_window("last_release", "month", _TODAY, _MIN, _MAX, rel, None)
    assert w.start == rel and w.end == _TODAY


def test_resolve_last_release_without_date_falls_back_to_span_min():
    w = _resolve_window("last_release", "month", _TODAY, _MIN, _MAX, None, None)
    assert w.start == _MIN


def test_resolve_current_week_starts_monday():
    w = _resolve_window("current", "week", _TODAY, _MIN, _MAX, None, None)
    assert w.start == dt.date(2026, 5, 11)        # Monday of that week


def test_resolve_current_month_starts_first():
    w = _resolve_window("current", "month", _TODAY, _MIN, _MAX, None, None)
    assert w.start == dt.date(2026, 5, 1)


def test_resolve_current_year_starts_jan1():
    w = _resolve_window("current", "year", _TODAY, _MIN, _MAX, None, None)
    assert w.start == dt.date(2026, 1, 1)


# ── PeriodWindow.sql_between ───────────────────────────────────────────────
def test_sql_between_valid_column():
    w = _resolve_window("current", "month", _TODAY, _MIN, _MAX, None, None)
    frag, params = w.sql_between("collected_at")
    assert "collected_at BETWEEN %s AND %s" in frag
    assert params == (w.start, w.end)


def test_sql_between_rejects_unknown_column():
    w = _resolve_window("current", "month", _TODAY, _MIN, _MAX, None, None)
    with pytest.raises(ValueError):
        w.sql_between("evil; DROP TABLE")


# ── _validate frozenset guards ────────────────────────────────────────────
def test_validate_rejects_bad_table():
    with pytest.raises(ValueError):
        _validate("not_a_table", "date", "artist_id")


def test_validate_rejects_bad_date_column():
    with pytest.raises(ValueError):
        _validate("apple_songs_history", "evil", "artist_id")


def test_validate_rejects_bad_artist_column():
    with pytest.raises(ValueError):
        _validate("apple_songs_history", "date", "tenant")


def test_validate_accepts_known_triplet():
    _validate("instagram_media", "timestamp", "artist_id")  # no raise
