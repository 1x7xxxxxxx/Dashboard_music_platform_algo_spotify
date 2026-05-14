# Brick 32 — Live user counter widget

## Objective

Display on streaMLytics two complementary signals: how many artists are using the platform **right now** (active sessions, ≤5 min heartbeat) and how many are **registered total** (active artists). Powers a small public-facing trust signal on the landing and a richer admin pulse on the home.

## Affected files

| File | Nature (new / modified) | Role |
|------|------------------------|------|
| `migrations/026_active_sessions.sql` | new | `active_sessions` table + index + cleanup helper |
| `src/database/saas_schema.py` | modified | Add `active_sessions` entry to `SAAS_SCHEMA` dict (idempotent CREATE) |
| `src/database/postgres_handler.py` | modified | Add `'active_sessions'` to `_ALLOWED_TABLES` (P1 SQL allowlist rule) |
| `src/dashboard/utils/live_pulse.py` | new | Public helpers : `bump_heartbeat(artist_id)`, `get_live_pulse() -> (live, total)` |
| `src/dashboard/auth.py` | modified | Call `bump_heartbeat(artist_id)` once per page load, throttled via `st.session_state` (only 1 DB write per 60s per session) |
| `src/dashboard/views/home.py` | modified | New `_section_live_pulse(db)` rendered near the top of `show()` |
| `src/dashboard/views/landing.py` OR `register.py` | modified | Public widget "X artistes utilisent streaMLytics" (count only, no PII) |
| `tests/test_live_pulse.py` | new | Unit tests : heartbeat upsert, TTL cutoff, counter query |
| `.claude/dev-docs/roadmap/checklist.md` | modified | Mark Brick 32 sub-tasks done as they close |

## Implementation steps

1. **Migration 026** — `active_sessions(artist_id PK NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE, last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW())` + index on `last_heartbeat DESC`. Idempotent (`CREATE TABLE IF NOT EXISTS`).
2. **Schema sync** — Add to `saas_schema.py` so fresh installs and `init_db.sql` include the table.
3. **Allowlist** — Add `'active_sessions'` to `_ALLOWED_TABLES` in `postgres_handler.py`.
4. **`live_pulse.py` helpers** :
   - `bump_heartbeat(db, artist_id)` — `INSERT … ON CONFLICT (artist_id) DO UPDATE SET last_heartbeat = NOW()`. Wrapped in try/except — heartbeat failure must never block the UI (same garde que `csv_upload_log` en Brick 31).
   - `get_live_pulse(db, ttl_minutes=5) -> tuple[int, int]` — returns `(live_count, registered_count)`. Two queries (or one UNION ALL).
5. **Auth integration** — In `auth.py:get_artist_id()` (or a fresh `bump()` called once per `show()`), guard with `if 'last_heartbeat_at' not in st.session_state or now - last > 60s: bump_heartbeat(); st.session_state['last_heartbeat_at'] = now`. Throttles to ≤1 DB write per 60s per Streamlit session, regardless of rerun frequency.
6. **Home section** — `_section_live_pulse(db)` renders 2 `st.metric` cards : "🟢 Active right now" (live count) and "👥 Total registered" (registered count). Add to `show()` after the freshness section (or wherever in flow makes sense to user).
7. **Public landing widget** — Single `st.metric` "X artists trust streaMLytics" near the top of the landing/register flow. **No PII**, just the registered count. Caps refresh to once per Streamlit cache TTL (10 min) to limit DB load on anonymous traffic.
8. **Tests** — `tests/test_live_pulse.py` :
   - heartbeat is upserted (verify row exists after first call)
   - heartbeat refreshes `last_heartbeat` on second call
   - `get_live_pulse` honors the 5-min TTL (insert row at NOW() - 10min → not counted)
   - `get_live_pulse` returns the correct registered count (mix of `active=TRUE` and `active=FALSE`)
9. **Roadmap update** — Tick the 4 sub-tasks under Brick 32 in `checklist.md`.

## Open decisions to confirm before step 1

1. **SEO-friendly name** for the public widget. Candidates from checklist :
   - "Platform Pulse" — concise, recurring tech industry term
   - "Live Activity" — generic but immediately understood
   - "Artist Network Activity" — domain-specific
   - "Live Community Stats" — community-oriented
   - *Tim's choice ?*
2. **Public widget placement** — landing page (anonymous visitors, SEO juice) only, or also on home for authenticated users ?
3. **Active session definition** — 5 min TTL is the default proposed in the roadmap entry. Confirm or override (longer TTL = more inflated "live" number).
4. **Heartbeat throttle** — 60s session_state guard reduces DB writes by ~10×. Acceptable or stricter (e.g. 30s) ?

## Risks / watch-outs

- **Streamlit rerun storms** — page reruns on every interaction. Without the session_state throttle, a user spamming filter buttons could trigger dozens of UPSERTs per minute. Mitigation : throttle in step 5.
- **Public-widget DB load** — landing page is anonymous, no auth gate. If traffic spikes (SEO link from social), unthrottled `get_live_pulse()` calls could hammer the DB. Mitigation : `@st.cache_data(ttl=600)` on the public-facing helper variant.
- **Stale rows accumulation** — `active_sessions` grows unboundedly (1 row per artist forever). Mitigation : either let it grow (cheap; max ~thousands of rows for this single-tenant-per-user use case) or add a weekly cron `DELETE FROM active_sessions WHERE last_heartbeat < NOW() - INTERVAL '30 days'`. Defer to follow-up if size becomes an issue.
- **Privacy** — public widget MUST never expose `name`/`slug` of any artist, just counts. Already in spec (step 7) ; flag in code review.

## Out of scope

- Real-time websockets / SSE — we accept "live = ≤5 min stale".
- Per-tier breakdowns ("X basic + Y premium online") — kept private if added later.
- Geographic / device breakdowns — not requested, not built.
- Showing the *identities* of online artists — explicitly out (privacy).
- Cleanup cron / TTL pruning — deferred until table actually grows large enough to matter.

## Verification

- Manual test : open 2 incognito sessions, log in as 2 different artists, verify home counter shows "2 live". Wait 6 min on one tab → counter shows "1 live".
- `pytest tests/test_live_pulse.py -v` passes.
- `python3 .claude/scripts/validate_rex.py` still passes (no regressions on existing tools).
- `ruff check src/dashboard/utils/live_pulse.py src/dashboard/auth.py src/dashboard/views/home.py` clean.
- DB load check : `pg_stat_statements` on `active_sessions` shows ≤1 INSERT-or-UPDATE per minute per active session.
