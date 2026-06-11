"""Multi-tenant isolation — artist_id_sql_filter is the shared scoping primitive.

Used across 29 view files. The danger: it returns ('', ()) for admin (no filter), so if
a NON-admin session ever yields artist_id=None the filter silently disappears and that
user sees every tenant's data. These DB-free tests pin the contract: a real artist scopes,
admin doesn't, and a malicious alias is rejected (the f-string interpolation path).
"""
import pytest

from src.dashboard import auth


def test_non_admin_artist_is_scoped(monkeypatch):
    monkeypatch.setattr(auth, "get_artist_id", lambda: 7)
    frag, params = auth.artist_id_sql_filter("t")
    assert frag == "AND t.artist_id = %s"
    assert params == (7,)


def test_no_alias_form(monkeypatch):
    monkeypatch.setattr(auth, "get_artist_id", lambda: 3)
    frag, params = auth.artist_id_sql_filter()
    assert frag == "AND artist_id = %s"
    assert params == (3,)


def test_admin_gets_no_filter(monkeypatch):
    # admin (artist_id None) legitimately sees all data — but this MUST be the only
    # path that yields an empty filter.
    monkeypatch.setattr(auth, "get_artist_id", lambda: None)
    assert auth.artist_id_sql_filter("t") == ("", ())


@pytest.mark.parametrize("bad_alias", ["t; DROP TABLE x", "t.x", "1t", "t-x", "t x"])
def test_malicious_table_alias_rejected(bad_alias):
    # Alias is validated BEFORE artist_id is read, so this raises regardless of session.
    with pytest.raises(ValueError):
        auth.artist_id_sql_filter(bad_alias)
