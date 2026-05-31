---
rex:
  - date: 2026-05-31
    issue: "adr wrote ADRs to ROADMAP.md (absent here) with boilerplate context from another project (CNC/OPC UA)"
    fix: "Repointed to docs/adr/ (the real ADR home: ADR-001..003 + ADR-TEMPLATE.md); rewrote context for streaMLytics"
    severity: warn
---

Add an Architecture Decision Record. ADRs live as individual files under
`docs/adr/` (the single source — there is no ADR table in any ROADMAP.md).

ADR subject: $ARGUMENTS

## What to do

1. List `docs/adr/` to find the highest existing `ADR-0NN-*.md` and determine the
   next number (currently ADR-001 … ADR-003 exist + `ADR-TEMPLATE.md`).

2. Read `docs/adr/ADR-TEMPLATE.md` and create `docs/adr/ADR-0NN-<slug>.md` from it:

```markdown
# ADR-0NN — <title>

**Date:** YYYY-MM-DD
**Status:** Accepted
**Decision:** <what was decided>
**Rationale:** <why>
**Alternatives considered:** <what else was evaluated, with trade-offs>
**Consequences:** <what this implies for the codebase / deployment>
```

3. If `CLAUDE.md` lists ADRs in its "Reference docs" table, add the new row there
   so the index stays current.

4. Tell the user: ADR-0NN created at `docs/adr/ADR-0NN-<slug>.md`.

## Context

ADRs in this project cover: roadmap file layout (ADR-001), schema lifecycle —
no Alembic / no repository pattern (ADR-002), the deferred React rewrite
(ADR-003). Typical domains: Streamlit vs React, PostgreSQL schema/migration
strategy, Airflow DAG patterns, ML pipeline + model-serving choices, Docker
Compose vs K8s, Railway vs Hetzner deployment, security/RGPD constraints.
