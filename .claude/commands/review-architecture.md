---
rex:
  - date: 2026-08-20
    issue: "Copied verbatim from the MSDR repo: it read two UNRENDERED bootstrap templates, listed modules absent here (acquisition.py, fanuc_reader.py), diffed Alembic revisions (ADR-002 rejects Alembic) and audited QuestDB measurements. No QuestDB here — it could not produce a true statement."
    fix: "Rewritten against this repo: the populated `.claude/dev-docs/architecture.md`, the real schema sources (init_db.sql + migrations/), and `make schema-check` which already compares prod to canonical — including constraints since 2026-08-20."
    ref: "error-classes.md config-status-file-unrendered; prod-canonical-schema-drift"
    severity: warn
---

Audit the architecture documentation against the actual state of this codebase.

## What to do

### Step 1 — Modules drift

For a repo-wide sweep, `Spawn code-architecture-reviewer` — that is precisely its
job (cold audit of the diagrams against the codebase), and it keeps the file
listing out of this context. Otherwise, inline:

Read `.claude/dev-docs/architecture.md` (the populated one — **not**
`architecture/macro_architecture.md`, which is an unrendered bootstrap template).

List what exists on disk: `src/collectors/`, `src/transformers/`, `src/database/`,
`src/utils/`, `src/dashboard/views/`, `src/api/routers/`, `airflow/dags/`.

For each module: ✅ present in a diagram · ❌ on disk but in no diagram ·
⚠️ in a diagram but gone from disk.

### Step 2 — Tables drift (canonical schema, no Alembic)

The schema is `init_db.sql` + `migrations/*.sql` — there is no ORM and no Alembic
(ADR-002 rejects both, deliberately). Extract the tables the architecture doc
claims and compare with `CREATE TABLE` across those SQL files.

### Step 3 — Prod ↔ canonical drift

Do not re-implement it: `make schema-check PROD_SSH=…` provisions a throwaway
canonical Postgres from `init_db.sql` + migrations, dumps prod, and diffs
**columns, constraints (PK/UNIQUE/FK) and unique indexes**. Report its output.

A constraint difference is not cosmetic: it changes which rows can coexist and
which `ON CONFLICT` targets resolve. Anything under `key:` or `uix:` is a
deployment-order question — see `migrations/065`'s banner.

### Step 4 — Docker services drift

Compare the services named in the architecture doc with `docker-compose.yml`
(gitignored, local) and `docker-compose.example.yml` (tracked). `test_compose_parity`
already guards the two against each other; this step is about the diagram.

### Step 5 — Multi-tenant claims

The architecture doc describes a multi-tenant model. Verify the two invariants
that actually broke in production:
- `python3 .claude/scripts/audit_tenant_writes.py` → every write names its tenant
- `python3 -m pytest tests/test_e2e_two_tenants.py -q` → no tenant receives another's data

## Output format

A checklist, one line per check, ✅ / ❌ / ⚠️.
End with `X issues found` and the next command to run, or
`Architecture docs are in sync with the codebase.`

## When to use

- After a refactor touching more than five files, or a new DAG / view / router
- Before inviting an artist to test (together with `make artist-preflight`)
- After a migration that changes a key — see step 3
