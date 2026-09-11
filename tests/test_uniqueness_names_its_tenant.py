"""A fresh database born from `init_db.sql` scopes every uniqueness to its tenant.

Type: Test
Uses: psycopg2, a live Postgres, init_db.sql
Depends on: init_db.sql
Persists in: nothing — the whole check runs inside a transaction that is rolled back

Why this exists
---------------
Migration 064 fixed this class in production in 2026-08: `youtube_videos` and
`youtube_channels` were UNIQUE on the platform id alone, so two artists touching
the same video did not get a row each — the second collection re-assigned the
first one's row and their data vanished from their own views. Two beta artists
saw it happen.

It was fixed **in production and nowhere else.** On 2026-09-11 the repository's
own DDL still declared the broken form in four places (`init_db.sql:704,734`,
`src/database/youtube_schema.py:18,60`). `init_db.sql` is mounted at
`docker-entrypoint-initdb.d`, so every fresh database — CI, a new dev machine, a
rebuild after a disaster — was **born with the bug** and stayed that way until
someone happened to run `make migrate`. A fix that lives only in a migration is
a fix the next fresh database undoes.

The sweep that found those four also found two tables migration 064 had missed
entirely, live in production: `youtube_comments` and `youtube_playlists`. Both
were empty, which is precisely why they were fixed the same day (migration 100):
at zero rows the constraint swap migrates no data.

Why this reads the CATALOGUE and not the DDL text
-------------------------------------------------
The first version of this guard matched `UNIQUE(...)` with a regex over
`init_db.sql`, and `test_a_guard_reads_structure_not_text` rejected it —
correctly. A text match cannot see a uniqueness introduced by `ALTER TABLE`, by
a bare `CREATE UNIQUE INDEX`, or split across lines it did not anticipate, and
it reads comments as if they were code.

So the guard asks the only authority on what the DDL actually builds: it runs
`init_db.sql` into a throwaway schema and reads `pg_index`. That is the effect,
not the artifact — the distinction this repository keeps paying for.

The exemption below matters as much as the rule
-----------------------------------------------
`ml_prediction_outcomes UNIQUE(prediction_id)` has the same shape and is not the
same thing: `prediction_id` references `ml_song_predictions(id)`, a SERIAL
surrogate already globally unique. "One outcome per prediction" is the intended
semantics, and adding `artist_id` would permit two. It is listed with its reason
so a later sweep does not "fix" it.

Mutation record — 2026-09-11: with `UNIQUE(video_id)` put back into
`init_db.sql`, this guard names `youtube_videos` and fails; with the fix, it
passes. It has been seen red on the defect it exists to catch.
"""
from __future__ import annotations

import os
import pathlib
import re
import socket

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_INIT_DB = _ROOT / "init_db.sql"
_DB_HOST, _DB_PORT = "127.0.0.1", 5433

_TENANT_COLUMNS = {"artist_id", "saas_artist_id"}

# table -> why its uniqueness legitimately omits the tenant.
# Add to this only with the reason, never to silence a report.
_EXEMPT: dict[str, str] = {
    "ml_prediction_outcomes":
        "prediction_id references ml_song_predictions(id), a SERIAL surrogate already "
        "globally unique; one outcome per prediction is intended, and adding artist_id "
        "would allow two.",
}


def _dsn() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        return {"dsn": os.environ["DATABASE_URL"]}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {
        "host": _DB_HOST,
        "port": _DB_PORT,
        "dbname": os.environ.get("DATABASE_NAME", "spotify_etl"),
        "user": os.environ.get("DATABASE_USER", "postgres"),
        "password": os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    }


def _ddl_without_preamble() -> str:
    """`init_db.sql` minus its first six lines.

    Those lines are `CREATE DATABASE spotify_etl \\gexec` and `\\c spotify_etl` —
    psql meta-commands, and the second one is not cosmetic: it reconnects to the
    real database whatever `-d` you passed, so pointing psql at a scratch
    database silently runs the whole file against production's neighbour. Found
    the hard way on 2026-09-11.
    """
    return "\n".join(_INIT_DB.read_text(encoding="utf-8").splitlines()[6:])


_CONN = _dsn()

pytestmark = pytest.mark.skipif(
    _CONN is None,
    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — building the schema is the check",
)


@pytest.fixture(scope="module")
def uniqueness_by_table() -> dict[str, list[tuple[str, list[str]]]]:
    """Build the schema in a throwaway namespace; return what Postgres actually made.

    Everything happens inside one transaction that is rolled back, so no
    database is created and nothing is left behind — not even on a failure.
    """
    psycopg2 = pytest.importorskip("psycopg2")
    schema = "ddlcheck_" + re.sub(r"\W", "", os.urandom(4).hex())

    conn = psycopg2.connect(**_CONN)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {schema}")
            # search_path excludes public on purpose: with public visible,
            # `CREATE TABLE IF NOT EXISTS` would find the real tables and skip,
            # and the guard would check nothing while looking green.
            cur.execute(f"SET LOCAL search_path TO {schema}")
            cur.execute(_ddl_without_preamble())

            cur.execute(
                """
                SELECT c.relname,
                       i.relname,
                       array_agg(a.attname ORDER BY k.ord)
                FROM pg_index x
                JOIN pg_class  c ON c.oid = x.indrelid
                JOIN pg_class  i ON i.oid = x.indexrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN LATERAL unnest(x.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
                WHERE n.nspname = %s AND x.indisunique AND NOT x.indisprimary
                GROUP BY c.relname, i.relname
                """,
                (schema,),
            )
            indexes = cur.fetchall()

            cur.execute(
                """
                SELECT c.relname
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relkind = 'r'
                  AND a.attname = ANY(%s) AND a.attnum > 0
                """,
                (schema, sorted(_TENANT_COLUMNS)),
            )
            tenant_scoped = {row[0] for row in cur.fetchall()}

        assert tenant_scoped, "no tenant-scoped table was built — the DDL did not run"
        return {
            "indexes": indexes,              # type: ignore[return-value]
            "tenant_scoped": tenant_scoped,  # type: ignore[dict-item]
        }
    finally:
        conn.rollback()                      # the schema never existed
        conn.close()


def test_every_tenant_scoped_table_scopes_its_uniqueness(uniqueness_by_table) -> None:
    offenders = [
        f"{table} — UNIQUE index {index} on ({', '.join(columns)}) omits the tenant. "
        f"Two tenants holding the same object cannot each keep a row."
        for table, index, columns in uniqueness_by_table["indexes"]
        if table in uniqueness_by_table["tenant_scoped"]
        and table not in _EXEMPT
        and not (set(columns) & _TENANT_COLUMNS)
    ]
    assert not offenders, (
        "A database born from init_db.sql enforces uniqueness on a platform id alone.\n"
        "This is the class migration 064 fixed after two beta artists lost their data,\n"
        "and 100 finished. Fix the DDL *and* ship a forward migration — a fix that\n"
        "lives only in a migration is undone by the next fresh database.\n\n"
        + "\n".join(sorted(offenders))
    )


def test_the_exemption_still_names_a_table_that_exists(uniqueness_by_table) -> None:
    """An exemption for a table that no longer exists silently widens the rule."""
    built = {table for table, _, _ in uniqueness_by_table["indexes"]}
    built |= uniqueness_by_table["tenant_scoped"]
    stale = sorted(set(_EXEMPT) - built)
    assert not stale, f"exempted table(s) the DDL no longer builds: {stale}"


def test_the_youtube_tables_are_the_ones_that_were_fixed(uniqueness_by_table) -> None:
    """Name the four sites, so a silent regression on them cannot pass as 'no offenders'.

    The general test above would also catch these, but only while the tables keep
    a tenant column and a unique index at all. Dropping either would make the
    general test green by having nothing to check — the failure mode this
    repository calls a predicate with no site.
    """
    by_table = {t: cols for t, _, cols in uniqueness_by_table["indexes"]}
    for table, platform_column in (
        ("youtube_videos", "video_id"),
        ("youtube_channels", "channel_id"),
        ("youtube_comments", "comment_id"),
        ("youtube_playlists", "playlist_id"),
    ):
        assert table in by_table, f"{table} has no unique index at all"
        columns = by_table[table]
        assert set(columns) & _TENANT_COLUMNS, f"{table}: UNIQUE({columns}) has no tenant"
        assert platform_column in columns, (
            f"{table}: UNIQUE({columns}) no longer constrains {platform_column}"
        )
