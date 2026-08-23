# ADR-012 — Lineage is out of scope at this scale; the tenant run log carries its weight

- **Status**: Accepted
- **Date**: 2026-08-23
- **Closes**: roadmap R44
- **Related**: ADR-007 (performance work is trigger-gated) — same shape of decision

## Context

Moses/Gavish/Vorwerck (*Data Quality Fundamentals*, p.144) list five pillars of data
observability: Freshness, Volume, Distribution, Schema, **Lineage**. After R39 and R42,
streaMLytics covers four:

| Pillar | Where it lives |
|---|---|
| Freshness | `freshness_monitor` + `etl_run_log` + `alert_monitor.check_data_freshness` |
| Volume | `check_row_anomalies` (spike) + `check_row_dips` (per-tenant dip, R39) |
| Distribution | `check_drift_anomalies` (ML features) + `check_spotify_data_consistency` behind its freshness circuit breaker (R42) |
| Schema | `notify_schema_drift.py`, cron 04h, class `prod-canonical-schema-drift` |
| **Lineage** | — nothing |

Lineage also appears at p.86 as the first of three conditions for a circuit breaker, so
leaving it implicit would leave R42 resting on an unstated dependency.

The honest question is not "would lineage be useful" — it would. It is whether the thing
lineage buys is already bought here by something cheaper.

## Decision

Lineage as a distinct capability (a graph of table-to-table derivation, maintained and
queried) is **out of scope** at this scale. The traceability it exists to provide —
"which collection produced these rows, for which tenant, when, and did it succeed" — is
carried by `etl_run_log`, one row per platform per tenant per run, and that is what
R42's circuit breaker actually stands on.

## Consequences

### Positive
- R42 no longer depends on an unbuilt pillar: its breaker reads `MAX(date)` on the source
  table, which is a fact, not an inference from a lineage graph.
- The decision is written down, so the gap is a choice rather than an oversight — the
  distinction `check_index_coverage.py` was just fixed for on the corpus side.

### Negative / Trade-offs
- A derived table breaking because an upstream one did will not be traced automatically;
  someone reads the DAG. With ~15 tables and one pipeline per platform, that is minutes.
- If a second consumer of the same tables appears (a public API, an export product), this
  ADR should be revisited: lineage earns its keep when the blast radius of a bad table is
  no longer knowable by reading one DAG.

### Neutral / Operational
- Trigger for revisiting, stated so it can actually fire: **more than one downstream
  consumer per source table**, or a data incident whose root cause takes more than an hour
  to attribute. Either one reopens this ADR.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Adopt an observability platform (Monte Carlo, Datafold…) | Cost and operational surface are an order of magnitude above the problem: six tenants, five platforms, one pipeline each. |
| Hand-maintained lineage in a YAML file | A registry restated by hand drifts from what runs — the class `audit-scope-restated-not-derived`, already catalogued here from a different instance. A wrong lineage is worse than none. |
| Derive lineage from SQL parsing | Real work, and it would answer a question nobody in this repo has yet had to ask. Deferred with a stated trigger rather than pre-built. |
