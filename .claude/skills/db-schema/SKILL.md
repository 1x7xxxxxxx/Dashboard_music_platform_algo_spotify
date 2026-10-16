---
name: db-schema
description: "Postgres schema and upsert conventions: tables, migrations, constraints, indexes and the PostgresHandler contract. Use when creating or altering a table, writing a migration, or when the user mentions schema, upsert, column, constraint, index or init_db. Not for query performance tuning and not for dashboard rendering. Assumes this project's PostgresHandler."
keywords: table, colonne, column, schéma, schema, migration, contrainte, constraint, index, upsert, init_db, alter table, create table, clé de conflit
---

# Skill: Database Schema

Injected when prompt contains: "schema", "upsert", "postgres", "table", "migration", "database"

---

## Relational Classification

- **Type**: Core
- **Depends on**: `src/database/postgres_handler.py`
- **Persists in**: PostgreSQL `spotify_etl`
- **Triggers**: `init_db.sql` (bootstrap) or `migrations/*.sql` via `make migrate` (existing DB)

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

## Where a table is declared

A table is declared in SQL, never in a Python module:

1. `migrations/NNN_<what>.sql` — idempotent (`CREATE TABLE IF NOT EXISTS`,
   `ADD COLUMN IF NOT EXISTS`), applied by `make migrate`;
2. the same `CREATE TABLE` in `init_db.sql`, so a fresh install gets it.

```sql
CREATE TABLE IF NOT EXISTS my_table (
    id              SERIAL PRIMARY KEY,
    artist_id       INTEGER NOT NULL REFERENCES saas_artists(id),
    some_key        VARCHAR(255) NOT NULL,
    some_value      DECIMAL(10,2),
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (artist_id, some_key)       -- must match conflict_columns
);
```

⚠️ No `src/database/<x>_schema.py` dict of DDL. Sixteen such modules existed until
R630 (2026-10-16): imported by nothing, they drifted from the migrations (the apple
unique key differed from `init_db.sql`) and pulled the database layer's coverage to
50 %. Guard: `python3 tools/dev/unreached_modules.py` (via
`tests/test_every_src_module_is_reached.py`). `ml_schema.py` and `stripe_schema.py`
stay because live code imports them.

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
| Existing database (add column, new table) | `migrations/NNN_*.sql` — idempotent, applied by `make migrate` |
| New table in existing DB | Add `CREATE TABLE IF NOT EXISTS` to `init_db.sql` AND write a migration |

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

- `meta_insights` UNIQUE is `(ad_id, date)` without `artist_id` — known P2 bug, collision risk
- `apple_songs_history` has no `artist_id` — data is shared across artists (P2 bug)

---

## Cross-Cutting Rules

1. **Language**: English in all DDL comments, Python comments, variable names
2. **Neutrality**: Document schema constraints factually — describe what the constraint enforces
3. **Classification**: a migration opens with a comment saying why it exists and what it changes
