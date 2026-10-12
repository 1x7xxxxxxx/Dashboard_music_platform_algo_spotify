# ADR-027 — One dashboard instance and no Redis, decided on 14 days of server curves

- **Status:** Accepted
- **Date:** 2026-10-12
- **Deciders:** the owner (R116, written only once its trigger fired), R114, R87
- **Extends:** ADR-026 (observability exists to watch triggers) and ADR-030 (scale by
  measured limits) — this is the decision those curves were collected for

## Context

R114 left the second Streamlit replica in an ambiguous state: its load test saturated
the CLIENT, so it could not say whether a replica helped. The replica was stopped on
both sides (Caddy upstream and Prometheus scrape), and the decision was deferred
until the SERVER-side render histogram (`streamlytics_rerun_duration_seconds`) had
14 complete days in `daily_ops_metrics`. That trigger fired on 2026-10-12.

Measured in production on 2026-10-12, before deciding:

| question | measure | source |
|---|---|---|
| complete days of server curves | **14** (2026-09-17 → 2026-10-11) | `SELECT count(*) FROM daily_ops_metrics WHERE complete` |
| render p50 per day | **27 – 100 ms** | `daily_ops_metrics.p50_render_ms` |
| view p95 per day | **83 – 925 ms**; worst 2026-09-23 (925), median day ~470 | `p95_view_ms` |
| chrome p95 (sidebar, routing) | **47 – 98 ms**, flat | `p95_chrome_ms` |
| peak concurrent sessions per day | **1 – 4** | `peak_sessions` |
| peak HUMAN sessions in one minute (180 d) | **6**, reopen threshold 20 | `make scale-check` |
| server render p50 over 12 renders | **59 ms**, reopen threshold 200 ms | `make scale-check` |
| pool high-water / direct fallbacks | 8 / up to 4 282 per day until 2026-09-24, then **1 / 0** | `pool_high_water`, `pool_direct_fallbacks` |
| Postgres connections | 15 in use of 100 | `pg_stat_activity` |
| host CPU / RAM peak | 11 – 34 % / 41 – 45 % | `cpu_max_pct`, `ram_max_pct` |

The pool line is not a capacity signal: the fallbacks were the API `/health` probe
holding the connection it borrowed, fixed by R215 on 2026-09-27. After the fix the
pool never went above one connection.

## Decision

Keep **one** dashboard instance and **no Redis**. The replica stays defined but
stopped (the three restart gestures stay above `reverse_proxy` in
`deploy/Caddyfile`), and both remain behind the triggers already watched every
night by `tools/dev/reopen_check.py`.

The reason is the curves, not a preference. The view p95 tail is real (up to
925 ms), but it does not come with concurrency: the worst days had 1 – 2 sessions,
and the chrome phase stays flat. A slow page at one session is a cost of that page.
A second process would not change it, because a replica splits sessions, not one
render.

## Consequences

### Positive
- One process, one in-memory cache, one set of rate limiters: R113 and R114's
  step 1 stay valid without a shared store.
- The tail is now named as a per-view cost. Fragmenting the five remaining views
  (`imusician`, `meta_ads_overview`, `hypeddit`, `youtube`, `admin`) is already
  gated on a 300 ms server view p50, under « Conditions d'attente ».

### Negative / Trade-offs
- A crash of the single instance takes the dashboard down until Docker restarts it.
  With 1 – 4 sessions this costs seconds, and buying redundancy against it would
  cost a second process at ~450 MB.
- The fourteen days hold at most 6 humans in one minute. This decision says nothing
  about 20, which is why the threshold stays watched rather than assumed.

### Neutral / Operational
- R116 leaves `reopen_check.py`: its trigger was the writing of this ADR. The trigger
  that reopens this decision is R114's (`tools/scale_check.sh`), which is still watched.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Start the replica now | peak 6 humans for a threshold of 20, p50 59 ms for 200 ms. The worst tail happened at 1 – 2 sessions, where a replica changes nothing |
| Redis for sessions and caches | Caddy's sticky affinity already keeps a session on its process; R113 removed the cache need and R114's step 1 removed the limiter need. No need was ever NAMED, and none of the 14 days shows one |
| Wait for 30 days before deciding | The load thresholds of R131 needed a distribution; this decision only needs the curves to be past the ambiguity of R114, and 14 days already show it. (R131 itself was closed the same day: Prometheus derives its thresholds from 28 days of history, group `streamlytics-load`) |
| Write the ADR on R114's client-side test | that measure saturated the client. This was the reason for deferring in the first place |

## How to reread this decision

`make scale-check PROD_SSH=root@167.233.92.1` gives the two thresholds:
- **> 20 human sessions in one minute**, or
- **a server p50 > 200 ms**.

Either one reopens this ADR. `make reopen-check-prod` runs it every night.
