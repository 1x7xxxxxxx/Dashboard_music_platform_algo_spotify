"""Pressing "Enregistrer" must never delete a secret the form cannot show.

Installed 2026-08-22. `_save_credentials` wrote `token_encrypted = EXCLUDED`, an
overwrite, while `_handle_save` computes an EMPTY blob whenever no *secret* field on
the tab holds a value. Two tabs declare no secret field at all:

    soundcloud → only `user_id`
    meta       → only `account_id` + `ig_user_id`

Both rows nevertheless carry a blob in production, written by something other than
the form:

    soundcloud → the rotated OAuth refresh_token (soundcloud_api_collector.py:132).
                 Without it the collector falls back to client_credentials and every
                 like count reads 0, with a green DAG.
    meta       → the System User token from tools/dev/inject_meta_token.py. It is the
                 credential EVERY tenant's Meta and Instagram collection uses.

So an admin opening the Meta tab, changing nothing, and pressing save destroyed the
platform's shared token. Silently — and the next night's DAG stayed green, because a
missing token skips tenants instead of failing.

These tests go through `_save_credentials`, the function the form actually calls, on
a real database. A test against a mock would have passed on the broken version: the
defect is in the SQL.
"""
import json
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

# What the two secret-less tabs send: a blank blob and a populated extra_config.
SECRETLESS_TABS = [
    pytest.param("soundcloud", {"user_id": "112904040"}, id="soundcloud"),
    pytest.param("meta", {"account_id": "act_1234567890"}, id="meta"),
]


@pytest.fixture
def tenant():
    """A throwaway tenant, removed afterwards."""
    from src.dashboard.utils import get_db_connection

    slug = f"secret-{uuid.uuid4().hex[:10]}"
    db = get_db_connection()
    artist_id = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (slug, slug),
    )[0][0]
    db.close()
    yield artist_id
    db = get_db_connection()
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


def _blob(db, artist_id: int, platform: str):
    rows = db.fetch_query(
        "SELECT token_encrypted FROM artist_credentials "
        "WHERE artist_id = %s AND platform = %s", (artist_id, platform),
    )
    return rows[0][0] if rows else None


@pytest.mark.parametrize("platform,extra", SECRETLESS_TABS)
def test_resaving_a_tab_with_no_secret_field_keeps_the_stored_secret(tenant, platform,
                                                                     extra):
    """The exact production shape: a blob exists, the tab sends ''."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.credentials._core import _save_credentials

    secret = "gAAAAAB-not-a-real-token-" + uuid.uuid4().hex  # pragma: allowlist secret
    db = get_db_connection()
    try:
        # Something other than the form put a secret here — the collector rotating a
        # refresh_token, or inject_meta_token.py.
        db.execute_query(
            "INSERT INTO artist_credentials (artist_id, platform, token_encrypted, "
            "extra_config) VALUES (%s, %s, %s, %s::jsonb)",
            (tenant, platform, secret, json.dumps(extra)),
        )
        assert _blob(db, tenant, platform) == secret, "fixture did not store the secret"

        # The artist edits their id and presses save. No secret field exists on this
        # tab, so `_handle_save` hands us ''.
        _save_credentials(db, tenant, platform, '', {**extra, "user_id": "999"})

        assert _blob(db, tenant, platform) == secret, (
            f"saving the {platform} tab destroyed the stored secret. That tab has no "
            "secret field, so it ALWAYS saves with an empty blob — for `meta` this is "
            "the System User token every tenant collects with."
        )
    finally:
        db.close()


@pytest.mark.parametrize("platform,extra", SECRETLESS_TABS)
def test_the_editable_fields_are_still_written(tenant, platform, extra):
    """Non-vacuity: keeping the secret must not mean the save did nothing."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.credentials._core import _save_credentials

    db = get_db_connection()
    try:
        _save_credentials(db, tenant, platform, '', extra)
        _save_credentials(db, tenant, platform, '', {**extra, "marker": "changed"})
        cfg = db.fetch_query(
            "SELECT extra_config FROM artist_credentials "
            "WHERE artist_id = %s AND platform = %s", (tenant, platform),
        )[0][0]
        cfg = json.loads(cfg) if isinstance(cfg, str) else cfg
        assert cfg.get("marker") == "changed", (
            f"extra_config was not updated for {platform} — the fix went too far and "
            "froze the whole row instead of only the secret"
        )
    finally:
        db.close()


def test_a_real_new_secret_still_replaces_the_old_one(tenant):
    """Keeping on empty must not become keeping on everything."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.credentials._core import _save_credentials

    db = get_db_connection()
    try:
        _save_credentials(db, tenant, "youtube", "first-blob", {"channel_id": "UC_a"})
        _save_credentials(db, tenant, "youtube", "second-blob", {"channel_id": "UC_a"})
        assert _blob(db, tenant, "youtube") == "second-blob", (
            "a genuinely new secret was refused — rotating an API key would be "
            "impossible from the form"
        )
    finally:
        db.close()


def test_the_tabs_that_carry_no_secret_field_are_the_ones_this_pins():
    """If a secret field is ever added to these tabs, this file's premise changes.

    Not a style check: the whole reason the defect existed is that these two tabs
    can never produce a non-empty blob. A future edit that gives `meta` a secret
    field should make someone re-read the reasoning above rather than silently
    changing what these tests mean.
    """
    from src.dashboard.views.credentials._registry import PLATFORMS

    secretless = {
        tab for tab, spec in PLATFORMS.items()
        if not any(f.get("secret") for f in spec["fields"])
    }
    assert secretless == {"soundcloud", "meta"}, (
        f"the set of secret-less tabs changed to {sorted(secretless)}. Re-read "
        "tests/test_saving_a_tab_never_destroys_a_secret.py — it exists because a tab "
        "with no secret field always saves an empty blob."
    )
