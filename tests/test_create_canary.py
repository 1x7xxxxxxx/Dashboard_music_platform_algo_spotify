"""The canary tool must refuse the two identities that would make it a lie.

Installed 2026-08-21 with `tools/create_canary.py`, which turns roadmap item R20
from "figure out the row, the flag and the credential shape" into one command.

The mechanical half is not the interesting part. These are:

  * **an identity equal to the admin's is refused.** A canary that points at the
    admin's own channel passes every check while the isolation it exists to prove
    is broken — the exact shape of the leak that filed every tenant's history
    under artist 1 for months. Silently accepting it would build a green light
    that means nothing.
  * **an identity another tenant already claims is refused**, matching what
    `find_identity_conflict()` does in the credentials form (R30). Two tenants on
    one identity is a state the product no longer allows; a CLI that creates it
    behind the form's back would reintroduce it.
  * **re-running is a no-op, not a refusal.** The uniqueness check has to exclude
    the canary itself, or the tool reports the canary as the tenant already
    claiming its own identity. It did exactly that until it was tried.

The tool's identity map must also stay in step with the credentials registry: a
platform that gains an identity field the tool cannot set produces a canary that
silently proves less than it claims.
"""
from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


def _repo_root() -> Path:
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
TOOL = REPO / "tools" / "create_canary.py"


def _run(*args: str):
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True, text=True, timeout=120, cwd=str(REPO),
    )


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection

    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def cleanup(db):
    slugs: list[str] = []
    yield slugs
    for slug in slugs:
        rows = db.fetch_query("SELECT id FROM saas_artists WHERE slug = %s", (slug,))
        for (artist_id,) in rows or []:
            db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (artist_id,))
            db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def test_it_creates_a_flagged_tenant(db, cleanup):
    suffix = uuid.uuid4().hex[:8]
    slug = f"canary-{suffix}"
    cleanup.append(slug)
    ident = f"sp-{suffix}"

    r = _run("--name", f"Canary {suffix}", "--slug", slug, "--spotify", ident)
    assert r.returncode == 0, r.stdout + r.stderr

    rows = db.fetch_query(
        "SELECT id, is_canary, active FROM saas_artists WHERE slug = %s", (slug,))
    assert rows, "the tenant was not created"
    artist_id, is_canary, active = rows[0]
    assert is_canary is True, "created without is_canary — preflight will not find it"
    assert active is True

    cred = db.fetch_query(
        "SELECT extra_config FROM artist_credentials WHERE artist_id = %s AND platform = 'spotify'",
        (artist_id,))
    cfg = cred[0][0] if isinstance(cred[0][0], dict) else json.loads(cred[0][0])
    assert cfg.get("spotify_artist_id") == ident


def test_rerunning_is_a_no_op_not_a_refusal(db, cleanup):
    """The canary must not be reported as the tenant already claiming its own id."""
    suffix = uuid.uuid4().hex[:8]
    slug = f"canary-{suffix}"
    cleanup.append(slug)
    ident = f"sp-{suffix}"

    first = _run("--name", f"Canary {suffix}", "--slug", slug, "--spotify", ident)
    assert first.returncode == 0, first.stdout + first.stderr

    again = _run("--name", f"Canary {suffix}", "--slug", slug, "--spotify", ident)
    assert again.returncode == 0, (
        "re-running refused itself:\n" + again.stdout + again.stderr
    )
    n = db.fetch_query("SELECT count(*) FROM saas_artists WHERE slug = %s", (slug,))
    assert n[0][0] == 1, "a second run created a second tenant"


def test_it_refuses_an_identity_another_tenant_already_claims(db, cleanup):
    suffix = uuid.uuid4().hex[:8]
    ident = f"sp-{suffix}"
    first, second = f"canary-a-{suffix}", f"canary-b-{suffix}"
    cleanup += [first, second]

    assert _run("--name", "A", "--slug", first, "--spotify", ident).returncode == 0
    r = _run("--name", "B", "--slug", second, "--spotify", ident)
    assert r.returncode == 1, "a second tenant took the same identity"
    assert "already claimed" in r.stdout, r.stdout
    assert not db.fetch_query("SELECT 1 FROM saas_artists WHERE slug = %s", (second,)), (
        "refused, but the tenant row was created anyway"
    )


def test_it_refuses_the_admins_own_identity(db, cleanup):
    """The refusal that stops the tool from producing a green light that lies."""
    # Whichever platform the admin actually declares — pinning one makes this
    # skip in any database where the admin uses a different mix, and a test that
    # skips on the real data is a test that never guards it.
    from src.dashboard.views.credentials._core import UNIQUE_IDENTITY_FIELDS

    found = None
    for platform, field in UNIQUE_IDENTITY_FIELDS.items():
        rows = db.fetch_query(
            "SELECT extra_config FROM artist_credentials "
            "WHERE artist_id = 1 AND platform = %s", (platform,))
        if not rows:
            continue
        raw = rows[0][0]
        cfg = raw if isinstance(raw, dict) else json.loads(raw or "{}")
        value = (cfg or {}).get(field)
        if value:
            found = (platform, str(value))
            break
    if not found:
        pytest.skip("artist 1 declares no platform identity at all in this database")
    platform, ident = found

    slug = f"canary-admin-{uuid.uuid4().hex[:8]}"
    cleanup.append(slug)
    r = _run("--name", "Copycat", "--slug", slug, f"--{platform}", ident)
    assert r.returncode == 1, "the tool accepted the admin's own identity"
    assert "admin" in r.stdout.lower(), r.stdout


def test_the_identity_map_matches_the_credentials_registry():
    """A platform the form knows and the tool does not yields a weaker canary."""
    sys.path.insert(0, str(REPO))
    import importlib.util

    spec = importlib.util.spec_from_file_location("create_canary", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from src.dashboard.views.credentials._core import UNIQUE_IDENTITY_FIELDS

    assert dict(mod._IDENTITY_FIELD) == dict(UNIQUE_IDENTITY_FIELDS), (
        "tools/create_canary.py and the credentials registry disagree on which "
        "field carries a tenant's identity:\n"
        f"  tool     {sorted(mod._IDENTITY_FIELD.items())}\n"
        f"  registry {sorted(UNIQUE_IDENTITY_FIELDS.items())}"
    )
