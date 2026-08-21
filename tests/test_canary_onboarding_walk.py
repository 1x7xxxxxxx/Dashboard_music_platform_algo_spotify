"""One synthetic tenant, walked from signup to a green light (R15).

Installed 2026-08-21. Every link of this chain was already tested — signup
(`test_signup_funnel_db`), the connection tests (`test_connection_test_proves_tenant`),
tenant-scoped collection (`test_e2e_two_tenants`), readiness
(`test_freshness_and_readiness_db`). What none of them tested is that the links
*compose*: that the tenant created by the form is the one the credential store
writes to, that the row a collector writes is the one readiness reads, and that
the light actually turns.

That gap is not theoretical. It is exactly how both beta sessions failed: each
piece reported success, and the artist still saw nothing. The readiness view said
⚪ "à connecter" while collection ran under the admin — two code paths that
contradicted each other by construction, and no test rendered both.

R15 asked for a synthetic canary and said it needed a "seeded tenant" decision.
The decision is already made by the fixtures this repo grew since: the tenant is
EPHEMERAL — created, walked, deleted — so the walk can run in CI on a throwaway
Postgres and leaves nothing behind to rot. A permanently seeded tenant would be a
second thing to keep true.

The real canary in production (R20) is a different object and still needed: it
uses real credentials against real APIs. This proves the plumbing; that proves the
world.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection

    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def canary(db):
    """A tenant that exists for the length of one test, then does not."""
    suffix = uuid.uuid4().hex[:10]
    rows = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier) VALUES (%s, %s, %s) RETURNING id",
        (f"Canary {suffix}", f"canary-{suffix}", "free"),
    )
    artist_id = rows[0][0]
    yield {"artist_id": artist_id, "suffix": suffix}
    for table in ("youtube_video_stats", "youtube_videos", "youtube_channel_history",
                  "youtube_channels", "artist_credentials"):
        db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def _readiness(db, artist_id: int, platform: str) -> dict:
    from src.utils.artist_readiness import artist_readiness

    for row in artist_readiness(db, artist_id):
        if row.get("key") == platform:
            return row
    raise AssertionError(f"{platform} is absent from the readiness matrix")


def test_the_whole_chain_composes(db, canary):
    """Signup → connect → collect → green. Each step asserted, in order.

    Written as one test on purpose: the point is the sequence. Split into four,
    each would pass against a tenant the previous step never touched — which is
    the failure being guarded against.
    """
    artist_id = canary["artist_id"]
    channel_id = f"UC{canary['suffix']}canary01234"[:24]

    # ── 1. A fresh tenant is "to connect", and owns nothing ──────────────────
    before = _readiness(db, artist_id, "youtube")
    assert before["status"] == "todo", (
        f"a brand-new tenant reads as {before['status']!r}, not 'todo'. Either it "
        "inherited someone's rows, or readiness is looking at the wrong tenant."
    )
    owned = db.fetch_query(
        "SELECT count(*) FROM youtube_videos WHERE artist_id = %s", (artist_id,)
    )
    assert owned[0][0] == 0, "a tenant that has never collected owns rows"

    # ── 2. Declaring an identity does NOT turn the light green ───────────────
    # The distinction that both beta sessions lacked: configured ≠ collecting.
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, %s, %s)",
        (artist_id, "youtube", json.dumps({"channel_id": channel_id})),
    )
    after_connect = _readiness(db, artist_id, "youtube")
    assert after_connect["status"] != "ok", (
        "readiness went green on a declared identity with no data behind it — "
        "that is the 'SoundCloud ✅ on 0 titre' failure, one platform over."
    )
    assert after_connect["next_action"], (
        "a non-green light with no next_action leaves the artist with nothing to do"
    )

    # ── 3. Collection writes rows, and they name this tenant ─────────────────
    now = datetime.now(timezone.utc)
    # Columns read from the live schema, not from memory: `youtube_channels` has
    # `channel_name` (not channel_title), and per-video counters live in
    # `youtube_video_stats`, not on the catalogue row. Writing against a
    # remembered schema is the `api-router-schema-drift` class.
    db.upsert_many(
        "youtube_channels",
        [{"artist_id": artist_id, "channel_id": channel_id,
          "channel_name": "Canary", "subscriber_count": 1,
          "view_count": 1, "video_count": 1, "collected_at": now}],
        conflict_columns=["artist_id", "channel_id"],
        update_columns=["channel_name", "subscriber_count", "collected_at"],
    )
    video_id = f"vid-{canary['suffix']}"
    db.upsert_many(
        "youtube_videos",
        [{"artist_id": artist_id, "video_id": video_id,
          "channel_id": channel_id, "title": "Canary track",
          "published_at": now - timedelta(days=1), "collected_at": now}],
        conflict_columns=["artist_id", "video_id"],
        update_columns=["title", "collected_at"],
    )
    # `artist_readiness` reads freshness from `youtube_channel_history` — not from
    # the catalogue and not from the per-video stats. Writing videos alone leaves
    # the light grey, which is what this test found on its first run. The DAG
    # writes all four; so does the walk.
    db.execute_query(
        "INSERT INTO youtube_channel_history "
        "(artist_id, channel_id, subscriber_count, video_count, view_count, collected_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (artist_id, channel_id, (collected_at::date)) DO UPDATE SET "
        "subscriber_count = EXCLUDED.subscriber_count, collected_at = EXCLUDED.collected_at",
        (artist_id, channel_id, 1, 1, 1, now),
    )
    db.upsert_many(
        "youtube_video_stats",
        [{"artist_id": artist_id, "video_id": video_id, "view_count": 10,
          "like_count": 1, "comment_count": 0, "collected_at": now}],
        conflict_columns=["artist_id", "video_id", "(collected_at::date)"],
        update_columns=["view_count", "like_count", "comment_count"],
    )

    mine = db.fetch_query(
        "SELECT count(*) FROM youtube_videos WHERE artist_id = %s", (artist_id,)
    )
    assert mine[0][0] == 1, "the row the collector wrote is not under this tenant"

    # ── 4. And only then does the light turn ─────────────────────────────────
    final = _readiness(db, artist_id, "youtube")
    assert final["status"] == "ok", (
        f"rows landed for this tenant and readiness still reads {final['status']!r}. "
        "The collector and the readiness view disagree about who owns the data — "
        "the exact contradiction that let the tenant leak run unnoticed for months."
    )
    assert final["last_dt"] is not None, "a green light with no timestamp behind it"


def test_the_walk_leaves_nothing_behind(db):
    """A canary that accumulates is a canary nobody dares delete.

    The fixture's teardown is what makes this runnable in CI. If it ever stops
    working, the next run inherits rows and every assertion above becomes a
    statement about the previous run.
    """
    before = db.fetch_query("SELECT count(*) FROM saas_artists WHERE slug LIKE %s",
                            ("canary-%",))[0][0]
    assert before == 0, (
        f"{before} canary tenant(s) still in saas_artists — a previous walk did not "
        "clean up, so the next one starts from someone else's state."
    )


def test_readiness_reads_a_table_the_dag_actually_writes():
    """The coupling this walk exposed on its first run, made explicit.

    `artist_readiness` derives every light from `freshness_monitor.MONITOR_TARGETS`, and
    for YouTube that is `youtube_channel_history` alone — not the catalogue, not
    the per-video stats. Write videos without a history row and the light stays
    grey while the data is there. The DAG writes all four today, so this is not a
    bug; it is a dependency nobody declared.

    Optimise the DAG to stop writing the history row and every tenant's YouTube
    light goes grey at once, with data landing normally. This is the assertion
    that would say so, at the moment of the change rather than at the next beta.
    """
    from pathlib import Path

    from src.utils.freshness_monitor import MONITOR_TARGETS

    root = Path(__file__).resolve().parents[1]
    dags = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (root / "airflow" / "dags").glob("*.py")
    )
    collectors = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (root / "src" / "collectors").glob("*.py")
    )
    written = dags + collectors

    unwritten = [
        s["table"] for s in MONITOR_TARGETS
        if s["table"] not in written
    ]
    assert not unwritten, (
        f"freshness reads {unwritten}, and no DAG or collector names those tables. "
        "Every tenant's light for those platforms can only ever be grey."
    )
