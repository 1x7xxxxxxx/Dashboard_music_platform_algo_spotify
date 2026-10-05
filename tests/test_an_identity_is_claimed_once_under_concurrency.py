"""Guard: two tenants saving the same platform profile at once — only one gets it (R370 b).

Type: Utility
Uses: threading, live Postgres
Triggers: pytest
Persists in: deux locataires jetables, effacés en fin de test

Error class `check-then-insert-loses-the-race`, sibling found by the 2026-10-05 sweep.

`find_identity_conflict` reads « does another tenant hold this id? » and the caller
then writes. Nothing in the schema forbids the duplicate (Meta is plural and sandboxes
are exempt, so no unique index can say it). Two signups pasting the same Spotify link
at the same moment both read « free » and both wrote: two dashboards on one artist's
streams. The check and the write now run in one transaction, serialised per identity
by an advisory lock (`tenant_identity.identity_claim`).
"""
from __future__ import annotations

import json
import os
import random
import socket
import string
import threading
import time
import uuid
from pathlib import Path

import pytest

from src.utils.tenant_identity import identity_lock_keys


def test_the_lock_keys_are_normalised_sorted_and_cover_meta_accounts() -> None:
    extra = {"account_ids": ["act_2", "1"], "ig_user_id": " 77 "}
    keys = identity_lock_keys(extra, ["meta", "instagram"])
    assert keys == sorted(keys)
    assert keys == ["meta:account:act_1", "meta:account:act_2", "meta:ig_user_id:77"]
    assert identity_lock_keys({"spotify_artist_id": ""}, ["spotify"]) == []


def _db():
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection(("127.0.0.1", 5433), timeout=1.5):
                pass
        except OSError:
            return None
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
        return db
    except Exception:  # noqa: BLE001
        return None


@pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")
def test_two_signups_with_the_same_spotify_link_give_it_to_one_tenant(monkeypatch) -> None:
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.credentials import _core
    from src.dashboard.views.credentials._from_signup import materialise

    admin = _db()
    spotify_id = "".join(random.choices(string.ascii_letters + string.digits, k=22))
    link = json.dumps({"spotify": f"https://open.spotify.com/artist/{spotify_id}"})
    tenants = []
    for _ in range(2):
        slug = f"race-id-{uuid.uuid4().hex[:8]}"
        tenants.append(admin.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active, pending_profile_links) "
            "VALUES (%s, %s, 'free', TRUE, %s::jsonb) RETURNING id",
            (f"RACE {slug}", slug, link))[0][0])

    # Widen the window between the check and the write, as a slow render would.
    real_check = _core.find_identity_conflict

    def slow_check(*args, **kwargs):
        found = real_check(*args, **kwargs)
        time.sleep(0.4)
        return found

    monkeypatch.setattr(_core, "find_identity_conflict", slow_check)
    barrier = threading.Barrier(2)
    errors: list[str] = []

    def worker(aid: int) -> None:
        db = get_db_connection()
        try:
            barrier.wait(timeout=30)
            materialise(db, aid)
        except Exception as exc:  # noqa: BLE001 — c'est l'objet de la mesure
            errors.append(repr(exc)[:200])
        finally:
            db.close()

    try:
        threads = [threading.Thread(target=worker, args=(a,)) for a in tenants]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert not errors, errors
        holders = admin.fetch_query(
            "SELECT artist_id FROM artist_credentials WHERE platform = 'spotify' "
            "AND extra_config->>'spotify_artist_id' = %s", (spotify_id,))
        assert len(holders) == 1, (
            f"{len(holders)} locataires détiennent le même profil Spotify — chacun "
            "lit les écoutes de l'autre")
    finally:
        for aid in tenants:
            admin.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (aid,))
            admin.execute_query("DELETE FROM saas_artists WHERE id = %s", (aid,))


@pytest.mark.parametrize("path", [
    "src/dashboard/views/credentials/_render.py",
    "src/dashboard/views/meta_extra_accounts.py",
])
def test_every_identity_writer_checks_under_the_claim(path: str) -> None:
    """R370 (audit) — the extra-ad-accounts page wrote `act_…` ids with NO conflict
    check: typing another tenant's account collected its spend. Each page writing a
    platform identity calls `find_identity_conflict` INSIDE `with identity_claim(…)`."""
    import ast

    tree = ast.parse((Path(__file__).resolve().parents[1] / path).read_text())
    inside = [
        node for w in ast.walk(tree) if isinstance(w, ast.With)
        for item in w.items
        if isinstance(item.context_expr, ast.Call)
        and getattr(item.context_expr.func, "id", "") == "identity_claim"
        for node in ast.walk(w)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "find_identity_conflict"
    ]
    assert inside, f"{path} writes an identity without a conflict check under identity_claim"
