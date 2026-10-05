"""Guard: two rotations of different secrets on one row keep BOTH keys (R370 c).

Type: Utility
Uses: threading, cryptography, live Postgres
Triggers: pytest
Persists in: un locataire jetable, effacé en fin de test

Error class `check-then-insert-loses-the-race`, sibling found by the 2026-10-05 sweep.

`update_platform_secret` read the encrypted blob, changed one key, re-encrypted and
wrote it back, in autocommit and without a lock. Two writers on the same row — the
Meta token refresh and the Instagram collector's rotation both write the `meta` row —
each wrote a blob holding only its own change: the other key was lost. And a blob that
failed to decrypt was replaced by `{key: value}`, erasing every other secret.
The read now takes `FOR UPDATE` in one transaction, and a decrypt failure aborts.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid

import pytest


def _db():
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection(("127.0.0.1", 5433), timeout=1.5):
                pass
        except OSError:
            return None
    try:
        from src.utils.credential_loader import _connect
        conn = _connect(autocommit=True)
        conn.cursor().execute("SELECT 1 FROM artist_credentials LIMIT 1")
        return conn
    except Exception:  # noqa: BLE001
        return None


pytestmark = pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")


@pytest.fixture
def tenant_row(monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)
    fernet = Fernet(key.encode())
    conn = _db()
    cur = conn.cursor()
    slug = f"race-secret-{uuid.uuid4().hex[:8]}"
    cur.execute("INSERT INTO saas_artists (name, slug, tier, active) "
                "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"RACE {slug}", slug))
    aid = cur.fetchone()[0]
    blob = fernet.encrypt(json.dumps({"kept": "k0"}).encode()).decode()
    cur.execute("INSERT INTO artist_credentials (artist_id, platform, token_encrypted) "
                "VALUES (%s, 'meta', %s)", (aid, blob))

    def secrets() -> dict:
        cur.execute("SELECT token_encrypted FROM artist_credentials "
                    "WHERE artist_id = %s AND platform = 'meta'", (aid,))
        return json.loads(fernet.decrypt(cur.fetchone()[0].encode()).decode())

    yield aid, secrets, cur
    cur.execute("DELETE FROM artist_credentials WHERE artist_id = %s", (aid,))
    cur.execute("DELETE FROM saas_artists WHERE id = %s", (aid,))
    conn.close()


def test_two_concurrent_rotations_keep_both_keys(tenant_row, monkeypatch) -> None:
    from cryptography.fernet import Fernet

    from src.utils.credential_loader import update_platform_secret

    aid, secrets, _cur = tenant_row
    real_encrypt = Fernet.encrypt

    def slow_encrypt(self, data):
        time.sleep(0.4)  # the window between the read and the write
        return real_encrypt(self, data)

    monkeypatch.setattr(Fernet, "encrypt", slow_encrypt)
    barrier = threading.Barrier(2)

    def rotate(name: str) -> None:
        barrier.wait(timeout=30)
        update_platform_secret(aid, "meta", name, f"{name}-new")

    threads = [threading.Thread(target=rotate, args=(n,)) for n in ("access_token", "refresh")]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    got = secrets()
    assert got == {"kept": "k0", "access_token": "access_token-new", "refresh": "refresh-new"}, (
        f"une rotation concurrente a perdu une clé : {sorted(got)}")


def test_an_undecryptable_blob_is_never_overwritten(tenant_row) -> None:
    from src.utils.credential_loader import update_platform_secret

    aid, _secrets, cur = tenant_row
    cur.execute("UPDATE artist_credentials SET token_encrypted = 'not-a-fernet-token' "
                "WHERE artist_id = %s AND platform = 'meta'", (aid,))
    update_platform_secret(aid, "meta", "access_token", "new")
    cur.execute("SELECT token_encrypted FROM artist_credentials "
                "WHERE artist_id = %s AND platform = 'meta'", (aid,))
    assert cur.fetchone()[0] == "not-a-fernet-token", (
        "un blob illisible a été remplacé par une seule clé — tous les autres secrets "
        "de la ligne sont perdus")
