# ADR-002 — No Alembic, no repository pattern, no observability stack

- **Status:** Accepted
- **Date:** 2026-05-14
- **Deciders:** @1x7xxxxxxx

## Context

A reference architecture from an internal Airbus project (`msdr_predictive_maintenance`, industrial safety-critical) was reviewed against the current streaMLytics layout. That reference uses, among other things:

- Alembic-managed schema migrations with versioned Python scripts
- A repository pattern in `database/repositories/` (one file per domain object)
- A `domain/` DDD layer separating business rules from data access
- A full observability stack (Prometheus + Grafana + OpenTelemetry collector)
- An `infra/` directory grouping all IaC and Docker configs
- A streaming pipeline (Redis Streams + MQTT + finite-state-machine consumers)
- Disaster Recovery automation (nightly pg_dump rotation, NAS rsync, DR rehearsal CI)

The question was whether streaMLytics should adopt any of these. The two projects are not comparable: msdr is hardware-attached, has machine-safety constraints, must replay deterministically against fixtures, and runs on customer IPCs with no operator on call. streaMLytics is a multi-tenant SaaS dashboard on top of a CRUD-heavy Postgres schema; it has no real-time control loop, no SLA below "best-effort", and 1 deploy target.

## Decision

streaMLytics rejects the following msdr patterns and continues with the existing simpler equivalents:

1. **Migrations**: keep flat `migrations/NNN_<topic>.sql` files (26 in place, all idempotent `CREATE … IF NOT EXISTS` / `ALTER TABLE IF EXISTS`). No Alembic.
2. **Data access**: keep `PostgresHandler` (psycopg2 wrapper with `_ALLOWED_TABLES` allowlist) called directly from views and collectors. No `database/repositories/` layer.
3. **Domain**: no `domain/` DDD layer. Business rules (artist filter, plan gate, role check) live in `src/dashboard/auth.py` and the views themselves.
4. **Observability**: keep `docker-compose logs` + the existing email alert system. No Prometheus / Grafana / OpenTelemetry.
5. **Infra dir**: keep the 3 Dockerfiles + `docker-compose.yml` at the repo root. No `infra/` subdir.
6. **Streaming**: no Redis Streams, MQTT, or FSM consumers. Data arrives by API polling (Airflow DAGs) or CSV upload — both batch, both already implemented.
7. **DR automation**: no nightly `pg_dump` rotation, NAS rsync, or DR rehearsal workflow. The current Postgres volume is on local Docker; backup/restore is operator-driven.

Three msdr patterns are **adopted** in the same review (see Brick 32 Phase B DEVLOG entry): `Makefile`, `pyproject.toml + uv`, and a split CI/CD into three workflows. Those carry low cost and clear benefit regardless of project criticality.

## Consequences

### Positive

- **Zero migration cost** on existing schema: 26 SQL files keep working; no risk of an Alembic env desync silently dropping a column.
- **Onboarding stays cheap**: one mental model (`db.fetch_df(sql, params)`), no repository / domain / service indirection to navigate.
- **No infra bloat**: a junior dev can boot the stack with `make up` and read everything in 30 minutes.
- **No false confidence**: the rejected items (DR rehearsal, Prometheus alerts) would *look* enterprise-grade without delivering value here — refusing them keeps expectations honest.

### Negative / Trade-offs

- **Schema rollback is manual**: reverting a botched migration means writing a reverse SQL by hand, no `alembic downgrade -1`.
- **Mocking in tests is heavier**: without a repository layer, tests mock `PostgresHandler` directly (cf. `test_postgres_handler.py`, `test_live_pulse.py`). Refactor cost grows with schema size — revisit if `_ALLOWED_TABLES` passes 100 entries (current: ~50).
- **Observability is reactive**: a slow query or rising error rate is only visible by tailing logs. If user complaints start arriving for latency reasons, this ADR is the first to revisit.
- **Coupling**: business rules sit next to render code (in views), so a non-trivial policy change touches the UI file. Acceptable while the policy set is small (artist filter, plan gate, role check); reconsider if the count doubles.

### Neutral / Operational

- Any new contributor reading this ADR should know: simpler is *deliberate*, not lazy. The msdr patterns are real, useful, and rejected here because the criticality budget doesn't justify them.
- If streaMLytics ever moves toward (a) regulated data (health/finance) or (b) multi-region with hard SLAs, this ADR is the trigger to re-evaluate Alembic + observability first.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Adopt msdr fully | Multi-week refactor with no user-visible benefit; risks breaking the 26-migration history. |
| Adopt Alembic only, keep the rest | Alembic shines when migrations are large and need rollback; here they are <50 lines each and the project has never needed a rollback in 32 bricks. |
| Adopt observability only | A Prometheus+Grafana stack here would be ~5 services in `docker-compose.yml` for two dashboards nobody watches. Defer until there is an actual operator role to consume them. |
| Adopt the repository pattern only | The win is mockability for tests — already achieved with `MagicMock(db.fetch_query)` (cf. `test_live_pulse.py`). Net zero benefit at this scale. |
