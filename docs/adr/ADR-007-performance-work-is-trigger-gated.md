# ADR-007 — Performance work is trigger-gated, not backlogged

- **Status:** Accepted
- **Date:** 2026-08-21
- **Deciders:** @1x7xxxxxxx

## Context

Four performance items sat in the active roadmap for months: caching four heavy
views, deferring plotly/sklearn/shap imports into the functions that use them, a
composite index on `s4a_song_timeline(artist_id, song, date)`, and splitting the
171 functions over 40 lines.

None of them was ever going to be done, and each already carried the reason
written next to it:

| Item | What was measured |
|---|---|
| Caching (`@st.cache_data(ttl=300)`, 4 views) | the queries run in **under 1 ms**; the real lever on load time is the Cloudflare edge cache, which is already in place |
| Composite index on `s4a_song_timeline` | `EXPLAIN ANALYZE` = **0.4 ms** over 13 794 rows via the existing `(artist_id, date)` index |
| Lazy imports | no per-view latency has ever been reported or measured |
| Splitting god-functions | the roadmap itself says **"au fil de l'eau, jamais en sweep dédié"** |

An item that is measured as unnecessary is not a task. Keeping it on the open
list costs a read at every `/resume` and `/sprint`, and — worse — it invites the
periodic temptation to "just do it", which would spend risk against a benefit
that was measured at zero. Two of the four would actively contradict a
measurement: caching a sub-millisecond query trades data freshness for nothing,
and adding an index that `EXPLAIN` says is unused adds write cost for nothing.

The fourth is different in kind. Splitting long functions is not gated on a
measurement but on **opportunity**: the right moment is when the function is
already open for another reason. A dedicated sweep across 171 functions is a
large diff with no behavioural test to catch what it breaks, which is the worst
possible shape for a refactor in a repo whose views are only covered by a
render-smoke.

## Decision

These four items leave the open roadmap and become **standing conditions**: work
starts when the named trigger fires, and not before. Each trigger is observable,
so nobody has to re-derive the judgement.

| Item | Trigger that reopens it |
|---|---|
| Caching on the 4 heavy views | concurrent traffic causing measurable re-render cost — i.e. more than one tenant using the dashboard at the same time, with a p95 that someone actually feels |
| Composite index on `s4a_song_timeline` | ~10× the current volume (≈140 k rows), or an `EXPLAIN ANALYZE` above ~50 ms on the real query |
| Lazy imports | a per-view cold-start latency reported by a user or measured above ~1 s |
| Splitting god-functions | **at the moment the function is being edited anyway** — never as a sweep |

## Consequences

### Positive
- The open roadmap holds only work that someone could start today. That is the
  property `/resume` depends on to be useful.
- The measurements survive. They were the expensive part; the list entries were
  not.
- Two mistakes are pre-empted: caching a sub-millisecond query, and indexing a
  path the planner does not use.

### Negative / Trade-offs
- A trigger nobody watches is a decision nobody revisits. Three of the four
  triggers are load-related and this product has one live tenant, so in practice
  they will fire when the first real traffic arrives — which is also when they
  will be obvious. That is acceptable; it would not be for a correctness item.
- Someone reading only the active roadmap will no longer see that caching was
  considered. This ADR is the record, and the archive entries point at it.

### Neutral / Operational
- `.claude/dev-docs/refactor-audit-dashboard.md` keeps the per-function detail
  for the day the god-function trigger fires on a specific file.
- This ADR does **not** cover `view_session()` adoption (roadmap R9). That one is
  a correctness question, not a performance one: measuring it found five views
  opening between two and five connections per render, which rule #9 forbids
  outright. It stays open, with `tests/test_view_connection_budget.py` holding
  the ceiling.

### Trigger review — 2026-08-30

The negative consequence above ("a trigger nobody watches is a decision nobody
revisits") was tested by reading all four against production. **None has fired.**

| Item | Measured 2026-08-30 | Verdict |
|---|---|---|
| Caching on the 4 heavy views | `s4a_song_timeline` has exactly **one** tenant that has ever deposited data | not fired |
| Composite index | **13 794 rows**, unchanged; the largest production table is 15 712 rows / 8 MB | not fired |
| Lazy imports | 6–77 ms per view **inside the production container** | not fired |
| Splitting god-functions | opportunity-gated, unchanged | — |

Two things this review established that the ADR did not say, and that the next
reader needs:

**1. Do not measure this on WSL.** The lazy-import trigger appeared fired when
measured from `/mnt/c`: 900–1250 ms per view, against a 1 s threshold. In the
production container the same imports cost 6–77 ms. `trigger_algo` renders in
9801 ms on WSL and 625 ms in production. A decision taken on the WSL numbers would
have spent risk against nothing.

**2. This ADR is about QUERIES, not about caching.** Its case against
`@st.cache_data` rests on a measurement of SQL — "the queries run in under 1 ms" —
and does not extend to CPU. `process_guide` was rendering two WeasyPrint PDFs on
every rerun (721 ms of its 1034 ms, production, same day), and the right fix there
was exactly `@st.cache_data`, because the output is a pure function of the session
language with no tenant data and nothing to go stale. See
`src/dashboard/utils/guide_assets.py` and the `download-payload-rebuilt-per-rerun`
error class. Reading this ADR as a ban on caching would have left that in place.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Do the four items now | Two contradict a measurement (0.4 ms query, <1 ms views); one has no measurement at all; one is explicitly the wrong shape as a sweep. Spending risk against a benefit measured at zero. |
| Leave them open with "DIFFÉRÉ" in the status column | That is what was done for months. It cost a read every session and never produced work — a status that never changes is not a status. |
| Delete them without a record | The measurements are the valuable part. Deleting them guarantees someone re-derives `EXPLAIN ANALYZE` on the same table in six months. |
