# ADR-030 — Scale by measured limits and watched triggers, not by anticipation

- **Status:** Accepted
- **Date:** 2026-09-28
- **Deciders:** the owner (night authorisations of 2026-09-27: « Mesurer, poser à 2× le pic »), R266
- **Extends:** ADR-007 (performance work is trigger-gated) — this ADR names the scalability triggers and who watches them

## Context

R266 (owner notes L72, L169, L549) asked for scalable ingestion and runtime: per-tenant
fan-out, a per-tenant API quota, container limits, a load test, zero lost rerun under
concurrency, the onboarding health N+1, and a pool sized for concurrency.

Measured on 2026-09-28, before deciding:

| question | measure | source |
|---|---|---|
| how close is the slowest DAG to its timeout | `meta_ads_api_daily` p95 **636 s** over 30 days = **6 %** of its 3 h `dagrun_timeout` | prod `airflow_db.dag_run` |
| how many tenants are collected | 5 active human tenants | prod `saas_artists` |
| container memory | peaks measured per container; **no container had a limit** | prod `docker stats` |
| onboarding health | **14 queries per tenant** (`artist_readiness`), ~700 at fifty tenants | query count on the dev base |
| Postgres connections | 15 in use of `max_connections = 100` | prod `pg_stat_activity` |
| lost reruns under concurrency | **0** — R114's four alternated passes: « A ne perd aucun rerun » | `archive.md`, R114 |

The last line contradicts the R266 row, which cited « 33-37 perdus »: that figure is
from before R114's measurement, and the measurement refuted it.

## Decision

Build what the measures show is a present risk, and turn every other item into a
**trigger watched every night** by `tools/dev/reopen_check.py`, never into anticipated
code.

Built now:

1. **Memory limits on every long-running container.** Set at about 2× the measured
   peak: postgres 1g, airflow-webserver 2560m, airflow-scheduler 6g (1.7×, the box has
   7.5 GiB), dashboard 900m, api 400m, prometheus 512m, grafana 256m, node_exporter 64m
   (13 MiB measured; a floor, not 2×). Applied live in production and in the versioned
   compose files. Guard: `tests/test_every_long_running_service_has_a_memory_limit.py`.
2. **The fleet readiness in a bounded number of queries.** `check_freshness_many` and
   `readiness_many` read identities, Spotify ids and every source's freshness once for
   the whole fleet (`ANY(%s) GROUP BY artist_id`), through the same `_result` / `_matrix`
   code as the per-tenant path. What still grows: the two expected-silence rules, asked
   only for a stale source, at most 3 queries per tenant (measured 14 → 50 queries for
   1 → 13 tenants, was 14 → 182). Guard:
   `tests/test_the_fleet_readiness_does_not_grow_with_tenants.py`.

Deferred behind a watched trigger:

| item | reopens when | watched by |
|---|---|---|
| per-tenant fan-out (dynamic task mapping) and a per-tenant quota budget | a production DAG's 30-day p95 passes **half** its `dagrun_timeout` (today 6 %) | `reopen_check.py` « fan-out par locataire » |
| load test at the ADR-007 threshold | `loadtest_dashboard.py -n 12` renders a p50 > 200 ms | `reopen_check.py` « R87 » |
| dashboard replica / lost reruns | one of the two thresholds of `tools/scale_check.sh` | `reopen_check.py` « R114 » |
| a larger pool (8 per dashboard instance) | Postgres connections in use pass 50 % of `max_connections` (today 15 %) | Grafana, `pg_stat_activity` |

## Consequences

### Positive
- A runaway task can no longer take the whole box: the kernel kills that container, not
  a random neighbour (Postgres was a candidate victim before).
- The onboarding health page stops growing at ~14 queries per tenant.
- Every deferred item has a number that reopens it; none depends on someone remembering.

### Negative / Trade-offs
- A limit set at 2× a peak can kill a container on a legitimate spike larger than
  anything seen so far. The scheduler, the riskiest, has 1.7× and the heaviest task
  history (108 215 task instances) behind its peak.
- The expected-silence rules still cost queries per tenant: batching them means
  batching the declared-ad-account fallback, and the conservative rule (« any doubt
  keeps the alert ») is not worth risking for 3 queries.

### Neutral / Operational
- The production compose file (`/opt/streamlytics/docker-compose.yml`, not versioned)
  was edited by hand; its backup is `docker-compose.yml.bak-r266-*` on the server.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Build the fan-out now | 6 % of the timeout with 5 tenants: roughly 8× more tenants before the trigger fires. Code that nothing exercises rots (ADR-007, `feedback_unwired_code_rots`) |
| Limits at 1.2× the peak | one legitimate spike kills the collection; 2× is the owner's decision |
| A query ceiling on the whole render | data-dependent: one more tenant turns it red with no code change (`a-threshold-written-on-instinct`); the slope per tenant is the invariant |
