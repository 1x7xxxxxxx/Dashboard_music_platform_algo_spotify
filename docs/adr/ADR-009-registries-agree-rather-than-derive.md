# ADR-009 — Two platform registries agree by test rather than derive from one another

- **Status**: Accepted
- **Date**: 2026-08-22
- **Closes**: roadmap R31

## Context

`src/utils/freshness_monitor.SOURCES_FOR_PLATFORM` is the registry that answers
"which table proves this platform is producing data". Four surfaces were derived from
it on 2026-08-22 after the measured incident that produced
`tests/test_platform_sources_agree.py`: Spotify was judged on four different tables
depending on the screen, so the same tenant read green on one page and red on
another, both truthfully. Deriving fixed that.

`src/dashboard/utils/kpi_helpers.SOURCES_CONFIG` is the fifth registry, and it was
left alone. R31 recorded the choice so it would be visible rather than look like an
oversight, and this ADR is that record in the place decisions live.

Two facts make it a different case from the other four:

* it carries sources readiness has **no opinion on** — `iMusician` today, and the
  panel is where a new distributor lands first;
* it does not merely name a table. Each entry carries `table`, `col`, `artist_col`
  and `artist_filter`, and those four feed the `frozenset` allowlists that make the
  panel's `UNION ALL` safe to build with an f-string (cross-cutting rule #8).

## Decision

`SOURCES_CONFIG` stays hand-written. The two registries are held in agreement by
test, not by derivation:

`tests/test_platform_sources_agree.py::test_the_kpi_panel_agrees_on_every_shared_source`
asserts that where both registries name the same source, they name the same table —
and, since 2026-08-22, that the number of shared labels does not fall below four.

## Consequences

**What this buys.** The drift that actually hurt — two surfaces judging one platform
on two tables — is impossible, because it is the thing asserted. A new distributor
can be added to the panel without touching a registry that four other surfaces read.

**What it costs.** A source that belongs in both must be added twice. That is a real
cost and it is the reason this ADR exists rather than a comment: the next person to
notice the duplication should find the decision, not rediscover the question.

**The failure mode this leaves open, and why it is acceptable.** Renaming a label on
one side removes it from the overlap, and the agreement check then compares fewer
things. That is exactly how a guard passes on nothing, so the floor of four shared
labels was added the same day the ADR was written; it fails on the rename instead of
going quiet.

**When to revisit.** If `SOURCES_CONFIG` ever stops carrying panel-only sources, the
argument above evaporates and derivation becomes the cheaper option.

## Alternatives considered

**Derive `SOURCES_CONFIG` from `SOURCES_FOR_PLATFORM`.** Rejected: it would change
the behaviour of a working `UNION ALL` and of the allowlists it builds, to remove a
duplication that a passing test already prevents from becoming a defect. A P4 with a
non-zero chance of breaking a live query is not worth doing.

**Add the panel-only sources to the freshness registry so both can derive.** Rejected
for a sharper reason: `SOURCES_FOR_PLATFORM` answers "is this platform collecting",
and iMusician does not collect — it is a CSV a human uploads. Adding it would make
the readiness matrix promise a green light nothing can produce, which is the class of
defect the whole freshness layer exists to remove.
