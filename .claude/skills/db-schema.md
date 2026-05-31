---
rex:
  - date: 2026-05-15
    issue: "New table written via upsert_many but not added to _ALLOWED_TABLES \u2192 cryptic\
  \ SQL-guard ValueError, DAG silently fails"
    fix: "Catalogued class unregistered-write-table + tests/test_allowed_tables_coverage.py\
  \ blocks CI; db-schema.md must document the _ALLOWED_TABLES registration step"
    severity: "warn"
    ref: "DEVLOG#2026-05-15"
  - date: 2026-05-29
    issue: "Unsure whether a global read-only reference table seeded via migration belongs in _ALLOWED_TABLES"
    fix: "Read-only reference tables (no upsert/insert) must stay OUT of _ALLOWED_TABLES (write-only guard); algo_lifecycle_benchmark is seeded via migration 035 + init_db.sql"
    severity: "info"
    ref: "DEVLOG#2026-05-29"
  - date: 2026-05-30
    issue: "New column radio_streams_forecast_7d: local tests passed but fresh installs + the\
  \ frozen pytest baseline broke"
    fix: "A new prediction column needs 5 synced edits: init_db.sql, create_missing_tables.sql,\
  \ a numbered migration, the DAG upsert update_cols, and the frozen baseline (regen\
  \ generate_ml_baseline.py)"
    severity: "warn"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-31
    issue: "Adding pi_forecast_7d showed '5 synced edits' was incomplete: ml_schema.py (ML_SCHEMA) had silently drifted"
    fix: "A new prediction column needs 6 synced points, not 5: also src/database/ml_schema.py. Audit that file for drift vs init_db.sql when touching ml_song_predictions; caught + backfilled radio + pi columns"
    severity: "warn"
    ref: "DEVLOG#2026-05-31"
---

# Skill: Database Schema

Injected when prompt contains: "schema", "upsert", "postgres", "table", "migration", "database"

---

## Relational Classification

- **Type**: Core
- **Depends on**: `src/database/postgres_handler.py`
- **Persists in**: PostgreSQL `spotify_etl`
- **Triggers**: `init_db.sql` (bootstrap) or `scripts/migrate_*.py` (existing DB)

---

## PostgresHandler Rules

| Rule | Detail |
|---|---|
| autocommit | `True` — never call `db.commit()` or `db.conn.commit()` |
| idempotent inserts | `upsert_many(table, data, conflict_columns, update_columns)` |
| append-only inserts | `insert_many(table, data)` — no UNIQUE constraint needed |
| read DataFrame | `db.fetch_df(sql, params)` |
| read list of tuples | `db.fetch_query(sql, params)` |
| raw SQL | `db.execute_query(sql, params)` |
| close | `db.close()` or context manager |

**Anti-patterns to avoid:**
- `db.conn.cursor()` directly — use `db.execute_query()` instead
- `db.conn.commit()` — autocommit is on, this creates inconsistency
- Raw `psycopg2` connection — always go through `PostgresHandler`

---

## Schema File Pattern

Reference: `src/database/youtube_schema.py`

```python
"""
Type: Sub
Depends on: postgres_handler.PostgresHandler
Persists in: PostgreSQL spotify_etl
"""

SCHEMA = {
    "my_table": """
        CREATE TABLE IF NOT EXISTS my_table (
            id              SERIAL PRIMARY KEY,
            artist_id       INTEGER NOT NULL REFERENCES saas_artists(id),
            some_key        VARCHAR(255) NOT NULL,
            some_value      DECIMAL(10,2),
            collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (artist_id, some_key)       -- must match conflict_columns
        )
    """,
}

def create_my_tables(db) -> None:
    for table_name, ddl in SCHEMA.items():
        db.execute_query(ddl)
```

---

## UNIQUE Constraint Rules

- Every table used with `upsert_many()` needs a `UNIQUE` constraint
- `conflict_columns` in `upsert_many()` must match the `UNIQUE` constraint columns **exactly**
- Multi-tenant tables: `UNIQUE` must include `artist_id`
- Verify with: `SELECT constraint_name, column_name FROM information_schema.key_column_usage WHERE table_name = 'my_table';`

---

## Bootstrap vs Migration

| Scenario | Mechanism |
|---|---|
| Fresh install (new Docker container) | `init_db.sql` — runs once at container startup |
| Existing database (add column, new table) | `scripts/migrate_*.py` — idempotent `ALTER TABLE IF NOT EXISTS` |
| New table in existing DB | Add `CREATE TABLE IF NOT EXISTS` to `init_db.sql` AND write a migration script |

---

## Table Taxonomy (avoid naming confusion)

| Table | Purpose |
|---|---|
| `saas_artists` | SaaS tenant table — `SERIAL` PK, `id`, `name`, `slug`, `tier` |
| `artist_credentials` | Fernet-encrypted API keys per artist per platform |
| `artists` | Spotify artist metadata — `VARCHAR` PK (Spotify artist ID) |
| `saas_artists.id` | The `artist_id` FK used across all multi-tenant tables |

---

## Watch-outs

- `hypeddit_schema.py` contains a `DROP TABLE` statement — never re-run on a live DB
- `meta_insights` UNIQUE is `(ad_id, date)` without `artist_id` — known P2 bug, collision risk
- `apple_songs_history` has no `artist_id` — data is shared across artists (P2 bug)
- `meta_campaigns` schema in DB has only 5 columns vs 11 in `meta_ads_schema.py` — P1 bug, needs migration

---

## Cross-Cutting Rules

1. **Language**: English in all DDL comments, Python comments, variable names
2. **Neutrality**: Document schema constraints factually — describe what the constraint enforces
3. **Classification**: Add docstring with Type/Depends on/Persists in at top of every new schema file
