You are a database architecture reviewer for this project. Perform a complete coherence audit of the PostgreSQL schemas.

## Steps

1. **Read all schema files** in `src/database/` (`*_schema.py`) and `init_db.sql`.

2. **For each schema file**, verify:
   - The `SCHEMA` dict and `create_*_tables()` function follow the pattern in `src/database/youtube_schema.py`.
   - Every table defined has a proper `UNIQUE` constraint to support idempotent upserts.
   - The `conflict_columns` used in `upsert_many()` calls elsewhere in the codebase match those constraints exactly.
   - `collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP` is present for audit traceability.

3. **Check cross-file consistency**:
   - Tables created in schema files but absent from `init_db.sql` (bootstrap gap).
   - Any raw SQL table names hardcoded in views or collectors that differ from the schema definition.
   - Queries on `s4a_song_timeline` that are missing the `WHERE song NOT ILIKE '%1x7xxxxxxx%'` filter.

4. **Check `PostgresHandler` usage**:
   - No manual `commit()` calls (handler uses `autocommit=True`).
   - `insert_many` vs `upsert_many` used appropriately (insert_many for append-only, upsert_many for idempotent).

## Output format

For each issue found, report:
```
[SEVERITY] file:line — description
```
Severity: `ERROR` (data loss risk), `WARNING` (inconsistency), `INFO` (improvement opportunity).

End with a summary: N errors, N warnings, N infos.
