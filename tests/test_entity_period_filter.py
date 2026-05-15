"""Unit tests for entity_period_filter pure logic (no Streamlit/DB)."""
import pytest
from src.dashboard.utils.period_filter import (
    EntitySpec,
    _entity_default,
    _entity_key,
    _validate_entity,
)

_OPTS = ["newest", "mid", "oldest"]  # release-DESC order


# ── _entity_default ───────────────────────────────────────────────────────
def test_default_multi_takes_latest_n():
    assert _entity_default(_OPTS, multi=True, n=2) == ["newest", "mid"]


def test_default_multi_n_floored_to_one():
    assert _entity_default(_OPTS, multi=True, n=0) == ["newest"]


def test_default_single_takes_latest():
    assert _entity_default(_OPTS, multi=False, n=3) == "newest"


def test_default_empty_multi_is_list():
    assert _entity_default([], multi=True, n=1) == []


def test_default_empty_single_is_none():
    assert _entity_default([], multi=False, n=1) is None


# ── _entity_key ───────────────────────────────────────────────────────────
def test_key_uses_primary():
    assert _entity_key("sc", "My Track") == "sc_My Track"


def test_key_falls_back_to_all():
    assert _entity_key("sc", None) == "sc_all"


# ── _validate_entity (frozenset guards) ───────────────────────────────────
def test_validate_accepts_known_spec():
    _validate_entity(EntitySpec("soundcloud_tracks_daily", "title", "collected_at"))
    _validate_entity(EntitySpec("apple_songs_history", "song_name", "date"))


def test_validate_rejects_bad_table():
    with pytest.raises(ValueError):
        _validate_entity(EntitySpec("evil_table", "title", "collected_at"))


def test_validate_rejects_bad_entity_column():
    with pytest.raises(ValueError):
        _validate_entity(EntitySpec("soundcloud_tracks_daily", "drop_me", "collected_at"))


def test_validate_rejects_bad_date_column():
    with pytest.raises(ValueError):
        _validate_entity(EntitySpec("apple_songs_history", "song_name", "evil"))


def test_entityspec_defaults():
    s = EntitySpec("soundcloud_tracks_daily", "title", "collected_at")
    assert s.multi is True and s.default_count == 1


def test_release_col_defaults_to_date_column():
    s = EntitySpec("soundcloud_tracks_daily", "title", "collected_at")
    assert s.release_column is None
    assert s._release_col == "collected_at"


def test_release_col_uses_release_column_when_set():
    s = EntitySpec("soundcloud_tracks_daily", "title", "collected_at",
                    release_column="track_created_at")
    assert s._release_col == "track_created_at"


def test_validate_accepts_allowlisted_release_column():
    _validate_entity(EntitySpec("soundcloud_tracks_daily", "title",
                                "collected_at", release_column="track_created_at"))


def test_validate_rejects_bad_release_column():
    with pytest.raises(ValueError):
        _validate_entity(EntitySpec("soundcloud_tracks_daily", "title",
                                    "collected_at", release_column="evil"))
