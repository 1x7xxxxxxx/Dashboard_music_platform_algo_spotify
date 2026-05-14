# Dashboard_music_platform_algo_spotify — Unified Roadmap

> Single source of truth for project status and planning.
> Priority: **P1** Blocking | **P2** Data integrity | **P3** UX/Features | **P4** Tech debt
> Last updated: $(date +%Y-%m-%d)

<!-- AUTO:STATS_BEGIN -->
<!-- AUTO:STATS_END -->

---

## Current Sprint

Active P1 items:
- [ ] TODO: fill in current sprint priorities

---

## Dev-Docs Index

| Deliverable | File | Content |
|-------------|------|---------|
| System architecture | `architecture/macro_architecture.md` | Mermaid system overview |
| Database schema | `architecture/database_schema.md` | Tables + ERD |
| Scripts reference | `architecture/scripts_reference.md` | Module inventory |
$([ "$FRAMEWORK" != "generic" ] && echo "| API endpoints | `api/endpoints.md` | Routes + params |")
$([ "$HAS_ML" -eq 1 ] && echo "| CI/CD | `mlops/cicd.md` | Tests, Docker, pipelines |")
| Alerting | `operations/alerting.md` | Thresholds + flows |
| Logging | `operations/logging.md` | Log levels + triggers |
| REX | `REX.md` | Lessons learned |

---

## Architecture Decision Records (ADRs)

> Append new ADRs via `/adr <title>`. Each ADR is numbered sequentially and immutable once merged.
> Template: `docs/adr/ADR-TEMPLATE.md` (use as starter for standalone ADR files).

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-000 | Bootstrap via setup-claude-code.sh | Standardised Claude Code config across org |
| [ADR-001](../../docs/adr/ADR-001-roadmap-multi-files-conserved.md) | Keep `roadmap/checklist.md` over baseline `ROADMAP.md` | Zero migration risk; existing slash commands/hooks still target it |
| [ADR-002](../../docs/adr/ADR-002-no-alembic-no-repository-pattern.md) | Reject Alembic, repository pattern, observability stack from msdr reference | Criticality budget doesn't justify the infra cost on a CRUD SaaS |

---

## Current Status ($(date +%Y-%m-%d))

### Implemented ✅
- TODO: list what works

### Blocked / Pending 🔵
- TODO: list blockers

---

## Completed Bricks

| Brick | Description | Tests |
|-------|-------------|-------|
| 01 | Project initialized | N/A |

---

## Active Development

### Brick 02 — TODO: First real feature
- [ ] P1 — TODO
- [ ] P2 — TODO

---

## Backlog

| Priority | Item | Notes |
|----------|------|-------|
| P3 | TODO | TODO |
