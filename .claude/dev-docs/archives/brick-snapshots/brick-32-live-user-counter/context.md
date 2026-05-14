# Brick 32 — Technical context snapshot — BRICK COMPLETE 2026-05-14

Captured 2026-05-14, post baseline merge (`f7b5fb0`), so the project conventions referenced here are current. **Brick shipped 2026-05-14** — see DEVLOG entry `2026-05-14 — Brick 32 : Live Activity widget`. This folder is kept for historical reference; `/resume` will skip it via the `BRICK COMPLETE` marker.

## Why this brick

Recorded in `.claude/dev-docs/roadmap/checklist.md` under "P3 — UX / Features (new, 2026-04-12)". Tied to the streaMLytics rebrand (commit `374c1b5`) — public-facing trust signals were called out as a marketing lever in the same session. The widget is meant to surface (a) an "alive" signal on the landing for SEO/trust, and (b) a small operational pulse on the home for the user/admin.

## Domain facts to keep in mind

- **Multi-tenant SaaS**, single PostgreSQL instance (`spotify_etl` db), one row per artist in `saas_artists` (id, slug, tier, active, created_at).
- `saas_artists` does NOT have a `last_active_at` or session timestamp column. Brick 32 introduces session state in a separate table on purpose — keeping identity (saas_artists) decoupled from activity (active_sessions).
- Streamlit reruns happen on every widget interaction → the heartbeat path must be throttled, not on every code re-execution.
- `auth.py:get_artist_id()` is called by every view, so it's the natural hook point (cf. all `views/*.py` import it). `is_admin()` is the admin check.

## Reference implementations to follow

- **Migration shape** : `migrations/025_csv_upload_audit_log.sql` is the freshest example — FK on `saas_artists`, idempotent `CREATE INDEX IF NOT EXISTS`, no destructive ops.
- **Schema dict pattern** : `src/database/saas_schema.py` lines 3–37 — `SAAS_SCHEMA = {'<table>': """CREATE TABLE …"""}` ; add the new table to this dict so it's part of the bootstrap.
- **SQL allowlist pattern (P1 rule)** : `src/database/postgres_handler.py:_ALLOWED_TABLES` — every new table name MUST be added here or `insert_many` / `upsert_many` will reject it. This is the same rule we touched in commit `ff055d3` (CSV upload audit log).
- **"Fire-and-forget audit write" pattern** : `src/dashboard/views/upload_csv.py:281–296` (the INSERT block we just merged) — the heartbeat helper should mirror this style (try/except, never block UI). Used as the canonical template for "auxiliary writes that must not affect UX on failure".
- **st.metric usage in home** : home.py already renders multiple `st.metric` instances in the freshness and KPI sections — reuse the existing styling for visual consistency.
- **Public unauthenticated surface** : `register.py` and the landing flow (handled in `app.py` routing). They run BEFORE `get_artist_id()` is hydrated, so the public widget must fetch counts without a session.

## Conventions already in place (don't re-decide)

- **Code in English**, comments and Streamlit user-facing strings can be FR (project bilingual rule, cf. project `CLAUDE.md` language section).
- **UTC-aware datetimes** for anything persisted (Notion/GSheets/GitHub rule from `.claude/rules/python.md`). For Postgres `TIMESTAMPTZ`, `NOW()` is fine — already returns UTC-aware.
- **Type hints required** on all new function signatures.
- **Max function length 40 lines**.
- **No bare except** — catch `psycopg2.Error` or specific exception, never `except:`.
- **No silent failures** — but the heartbeat write is an explicit exception (cf. plan step 4 and the upload_csv pattern). Document the rationale in a one-line comment at the catch site.

## Current state vs what's missing

- ✅ The roadmap entry is in place (`checklist.md` lines 231–237, just committed).
- ✅ Project tooling reset — baseline v2026.05.11 merged, REX validator passes, `.setup-version` stamped.
- ❌ No `active_sessions` table exists.
- ❌ No heartbeat helper anywhere in the codebase (grepped : no `last_seen`, `last_active`, `heartbeat`, `presence` patterns).
- ❌ The public landing widget — needs the entry-point file confirmed (look at `app.py` routing for the unauthenticated route).
- ❌ Brick 32 sub-tasks in `checklist.md` are 4 unchecked items — all to tick on completion.

## Files already read this session

- `src/database/saas_schema.py` (full)
- `src/dashboard/views/home.py` (head + structure scan)
- `src/database/postgres_handler.py` (referenced via diff in Brick 31)
- `.claude/dev-docs/roadmap/checklist.md` (full)
- `migrations/025_csv_upload_audit_log.sql` (reference shape)

## Open questions to answer before coding

1. **SEO-friendly name** for the public widget (4 candidates in plan §"Open decisions").
2. **Public widget placement** : landing only, or also home ?
3. **Active session TTL** : 5 min (roadmap default) or other ?
4. **Heartbeat throttle interval** : 60s session_state guard (recommended) or stricter ?

The plan answers all four with defaults but does not commit until the user confirms — typing "go with defaults" or specifying overrides moves Brick 32 from PLAN to IN PROGRESS.
