---
globs: ["**/*.py"]
rex:
  - date: 2026-07-06
    issue: "Ingest-latency instrumentation did a SYNCHRONOUS Redis XADD on the ingestion hot path (acquisition._persist_frame with a PG pool conn checked out; rib_reader.persist inside sync_joiner's budget); and the 11 redis.Redis.from_url sites passed no retry= → a redis-py 8.x bump would turn socket_timeout into a 30s+ blocking call."
    fix: "Sink made fire-and-forget (bounded queue + background daemon thread, drop-on-full — zero network I/O on the hot path); centralized infra/redis_client.py::make_redis_client factory pinning retry=Retry(NoBackoff(),0)+retry_on_timeout=False across all 11 sites; error-class redis-retry-policy-unpinned + grep gate + tests/test_redis_client_factory.py."
    ref: "DEVLOG#2026-07-06; error-classes.md redis-retry-policy-unpinned"
    severity: crit
---

# Python conventions — MSDR

- Follow PEP8; ruff (E, F, W) is the linter — no manual style overrides
- Type hints required on all function signatures (args + return type)
- No bare `except:` — always catch a specific exception class
- **All Redis clients via `infra/redis_client.py::make_redis_client`** — never raw `redis.Redis.from_url(` (error-class `redis-retry-policy-unpinned`). The factory pins a no-retry policy so an unpinned redis-py major bump can't turn `socket_timeout` into a 30 s+ blocking call in a real-time loop.
- **No blocking network I/O in the ingestion hot path** (`acquisition`, `rib_reader`, `redis_consumer`, `sync_joiner`, `phase_state_machine`) or while a PG pool connection is checked out — instrumentation / side-effects must be fire-and-forget (bounded queue + background thread), else they reproduce the B54 Phase C pool-exhaustion / sync-staleness class.
- No f-strings in SQL queries — parameterized queries only (`?` placeholders)
- Max function length: 40 lines. Extract helpers if exceeded.
- No mutable default arguments (`def f(x=[])` → `def f(x=None)`)
- Imports: stdlib → third-party → local, one blank line between groups
- Docstrings: one short line max, only when the purpose is non-obvious from the name
- Timestamps written to DB or returned from API handlers must be UTC-aware: `datetime.now(timezone.utc).isoformat(timespec="milliseconds")`. Bare `datetime.now()` is forbidden outside purely cosmetic contexts (email body strftime, PDF header, filename suffix) that never persist. Rationale: brick `sync-phase-0-clock-hygiene` — bare `datetime.now()` is host-TZ-naïf, breaks `fetch_plc_context_at` ±500ms window on non-UTC containers, and produces ambiguous strings that silently mis-order vs aware `+00:00` siblings under lexicographic comparison.
