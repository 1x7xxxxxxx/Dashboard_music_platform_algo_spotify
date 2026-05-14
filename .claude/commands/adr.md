---
rex: []
---

Add an Architecture Decision Record to ROADMAP.md.

ADR subject: $ARGUMENTS

## What to do

1. Read `.claude/dev-docs/ROADMAP.md` to find the current ADR list and determine the next ADR number.

2. Append the new ADR row to the ADR table in ROADMAP.md:

```
| ADR-NNN | <decision title> | <rationale — one sentence> |
```

3. If the decision has notable alternatives considered or consequences, append a detail block **after** the ADR table:

```markdown
### ADR-NNN — <title>
**Date:** YYYY-MM-DD
**Decision:** <what was decided>
**Rationale:** <why>
**Alternatives considered:** <what else was evaluated>
**Consequences:** <what this implies for the codebase / deployment>
```

Only add the detail block if the decision is non-obvious or has significant trade-offs. For straightforward decisions, the table row alone is sufficient.

4. Tell the user: ADR-NNN added to ROADMAP.md.

## Context

ADRs in this project cover: storage choices (<your time-series DB> + PostgreSQL), CNC connectivity (<your CNC> OPC UA), infrastructure (Docker Compose vs K8s), ML pipeline choices, security constraints (<your organization> IT/OT), deployment decisions, schema lifecycle (Alembic, ADR-018).
