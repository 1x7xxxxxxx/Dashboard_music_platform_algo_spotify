---
rex: []
---
<!--
  NOTE: this file lives outside the validate_rex.py walk dirs
  (.claude/{agents,skills,commands,rules,hooks,scripts}), so the `rex:` block
  above is DOCUMENTARY only — it is not schema-validated. Durable lessons about
  error classes are recorded in the per-tool REX of the guard that closes them
  (see each class's `rex_ref`).
-->

# Error-class catalogue — single source of truth

Every recurring bug is abstracted here into a **class** with a **machine-detectable
signature**. `/sweep`, `make audit`, and `.claude/hooks/suggest_sweep.py` all
consume `signature.cmd` literally — signature logic lives nowhere else.

## Contract

- `signature.cmd` is a self-contained shell command run from the repo root that
  **exits non-zero when the anti-pattern is present** (a "hit"). The idiom
  `! grep -rnE '<pat>' <path>` satisfies this: grep prints the offending lines,
  the leading `!` makes the exit code non-zero on a hit.
- `kind: deterministic` → zero false positives, safe to block CI.
  `kind: heuristic` → grep approximation with known false positives, runs
  nightly non-blocking only.
- `autofix: safe` → `/sweep` Phase 4 may apply the mechanical fix to the exact
  hits. `autofix: none` → report-only (semantic; never rewrite unasked).
- Entries are append-only. Status changes / corrections = a new line in the
  class's **History**, never an in-place rewrite.

## Per-class schema

```
## CLASS-ID
- status:    guarded | reported | open
- severity:  P1 | P2 | P3 | P4        (CLAUDE.md Cross-Cutting Rule #4)
- kind:      deterministic | heuristic
- symptom:   one line — the observed failure
- signature: `<exact shell command, exit!=0 on hit>`
- autofix:   safe | none
- guard:     { type: <ci-step|pre-commit|posttooluse-hook|ruff-rule|make-precondition|cross-cutting-rule>, ref: <path> }
- rex_ref:   <path to the tool whose rex: block records the durable lesson>
- first_seen: YYYY-MM-DD  (ref: DEVLOG#YYYY-MM-DD)
- History:
  - YYYY-MM-DD: <status transition / note>
```

## Index

| CLASS-ID | sev | kind | status | autofix |
|---|---|---|---|---|
| [streamlit-pin-drift](#streamlit-pin-drift) | P1 | deterministic | guarded | safe |
| [make-fail-late](#make-fail-late) | P3 | heuristic | reported | none |
| [collector-silent-success](#collector-silent-success) | P2 | heuristic | guarded | none |
| [artist-id-or-1](#artist-id-or-1) | P1 | deterministic | open | none |
| [sql-fstring-identifier](#sql-fstring-identifier) | P1 | heuristic | open | none |
| [db-connection-per-show](#db-connection-per-show) | P3 | heuristic | open | none |
| [naive-datetime-now](#naive-datetime-now) | P2 | heuristic | open | none |
| [df-na-rep](#df-na-rep) | P3 | heuristic | guarded | none |
| [unregistered-write-table](#unregistered-write-table) | P2 | deterministic | guarded | none |
| [view-session-adoption](#view-session-adoption) | P4 | heuristic | open | none |
| [mixed-date-timestamp](#mixed-date-timestamp) | P2 | heuristic | guarded | none |
| [collector-shipped-dag-not-rerun](#collector-shipped-dag-not-rerun) | P3 | heuristic | open | none |
| [ingest-time-as-release-date](#ingest-time-as-release-date) | P3 | heuristic | guarded | none |
| [operator-guidance-phantom-or-wrong-auth](#operator-guidance-phantom-or-wrong-auth) | P3 | heuristic | guarded | none |
| [object-dtype-numeric-op](#object-dtype-numeric-op) | P3 | heuristic | guarded | none |
| [tz-aware-naive-mix](#tz-aware-naive-mix) | P3 | heuristic | guarded | none |
| [snapshot-fixture-hook-reflow](#snapshot-fixture-hook-reflow) | P3 | deterministic | guarded | none |
| [song-name-convention-mismatch](#song-name-convention-mismatch) | P2 | heuristic | guarded | none |

---

## streamlit-pin-drift
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a package pinned `==X` in one manifest while another manifest / the lockfile / the installed env pins `==Y` → prod≠dev, "works locally breaks in Docker".
- signature: `python3 tools/dev/check_manifest_consistency.py`
- autofix: safe
- guard: { type: ci-step, ref: .github/workflows/ci.yml }
- rex_ref: tools/dev/check_manifest_consistency.py
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: discovered (streamlit 1.29.0 manifests vs 1.54.0 installed); guard wired (Makefile `check-manifest`, pre-commit, ci.yml blocking step).

## make-fail-late
- status: reported
- severity: P3
- kind: heuristic
- symptom: a Makefile target invokes a runtime dependency (Docker / venv / Postgres / `uv` / `streamlit`) and crashes mid-execution instead of failing fast with an actionable message.
- signature: `! grep -nE "^\t.*(docker|streamlit|psql|uv )" Makefile | grep -vE "check-env|check-manifest"`
- autofix: none
- guard: { type: cross-cutting-rule, ref: .claude/rules/makefile-fail-fast.md }
- rex_ref: .claude/rules/makefile-fail-fast.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: discovered (`make dashboard` crashed on first render when Postgres down); fixed via `dashboard: check-env`. Rule #10 documents the convention. First sweep: `up`, `logs`, `test` invoke runtime deps without a precondition prerequisite — report-only, manual triage (not auto-rewritten).

## collector-silent-success
- status: guarded
- severity: P2
- kind: heuristic
- symptom: a collector `except` block logs then returns empty (`None`/`[]`/`{}`) → DAG upserts 0 rows, exits SUCCESS, no alert, dashboard silently stale.
- signature: `! grep -n "return None\|return \[\]\|return {}\|return tracks\|return stats\|return data" src/collectors/*.py`
- autofix: none
- guard: { type: posttooluse-hook, ref: .claude/skills/audit-collectors.md }
- rex_ref: .claude/skills/audit-collectors.md
- first_seen: 2026-03-25 (ref: DEVLOG#2026-03-25)
- History:
  - 2026-03-25: 8 files audited + fixed (see audit-collectors.md table).
  - 2026-05-15: catalogued. Fix guidance stays in audit-collectors.md (rules 1–4); this entry is the machine-detectable index only.
  - 2026-05-15: regression — `youtube_collector.get_video_comments` (l.242) + `get_playlists` (l.296) caught `except Exception`, logged, then `return comments`/`return playlists` (partial collection). Missed by the 2026-03-25 sweep (only get_channel_stats/videos/video_stats were fixed; the audit-collectors.md status table over-claimed YouTube fully done). Both → `raise`. Note: `get_channel_stats:43-45` / `get_channel_videos:93-95` `return None`/`return videos` on a *successful* empty-`items` response are a distinct case (not an `except` block) — left for a dedicated pass.
  - 2026-05-15: re-sweep post-fix. AST scan ("any non-raising `return` inside an `except` in `src/collectors/*.py`") = the precise detector — confirms youtube l.242/296 now raise project-wide; **0 real instances remain**. The catalogued grep signature is confirmed `heuristic`: noisy (11 hits, ~all legit success-path `return data`/`return tracks`) AND was blind to the partial-return variant (`return comments`/`return playlists`) — the AST scan supersedes it as the re-verification tool (signature line kept append-only; not rewritten — guard is the PostToolUse hook + audit-collectors skill, not this grep). Accepted false-positive: `instagram_api_collector.py:105` `return False` in `except` of `_refresh_access_token()` — a bool-STATUS helper (contract IS bool; `_check_proactive_refresh` calls it best-effort, no upsert depends on it), NOT the data class. Documented FP shape: bool/None-status helpers vs data-returning fetch methods. Class stays `guarded`.

## artist-id-or-1
- status: open
- severity: P1
- kind: deterministic
- symptom: `get_artist_id() or 1` coerces an unhydrated session onto artist 1 → cross-tenant data leak (CLAUDE.md rule #7).
- signature: `! grep -rnE "=[[:space:]]*get_artist_id\(\)[[:space:]]+or[[:space:]]+1" src/`
- autofix: none
- guard: { type: cross-cutting-rule, ref: CLAUDE.md#7 }
- rex_ref: CLAUDE.md
- first_seen: 2026-03-27 (ref: DEVLOG#2026-03-27)
- History:
  - 2026-03-27: 9 views fixed with explicit guard. Pattern still ungrepped in CI until now.
  - 2026-05-15: catalogued, added to `make audit`.
  - 2026-05-15: no-arg /sweep caught a FALSE POSITIVE — the prior signature `get_artist_id() *or *1` matched the `view_session()` docstring + CLAUDE.md rule text that *quote* the anti-pattern, breaking the `deterministic` (CI-safe) contract. Hardened to require assignment context `= get_artist_id() or 1` (verified 0 real hits, docstring excluded). `make audit` recipe synced to the same regex (no catalogue↔audit drift).

## sql-fstring-identifier
- status: open
- severity: P1
- kind: heuristic
- symptom: a table/column name interpolated into SQL via f-string without `frozenset` allowlist validation (CLAUDE.md rule #8) → SQL injection.
- signature: `! grep -rnE "f\"\"\"?[^\"]*(FROM|JOIN|INTO|UPDATE|TABLE) +\{" src/ --include=*.py`
- autofix: none
- guard: { type: cross-cutting-rule, ref: CLAUDE.md#8 }
- rex_ref: CLAUDE.md
- first_seen: 2026-03-28 (ref: DEVLOG#2026-03-28)
- History:
  - 2026-05-15: catalogued. Heuristic — manual triage required (value `%s` params are fine; only identifier interpolation is the bug).

## db-connection-per-show
- status: open
- severity: P3
- kind: heuristic
- symptom: a Streamlit view opens >1 DB connection per `show()` instead of one opened-then-closed-in-finally (CLAUDE.md rule #9).
- signature: `! for f in $(grep -rl get_db_connection src/dashboard/views/); do n=$(grep -c "get_db_connection(" "$f"); [ "$n" -gt 1 ] && echo "$f: $n"; done | grep .`
- autofix: none
- guard: { type: cross-cutting-rule, ref: CLAUDE.md#9 }
- rex_ref: CLAUDE.md
- first_seen: 2026-03-27 (ref: DEVLOG#2026-03-27)
- History:
  - 2026-05-15: catalogued. Heuristic — a view legitimately may call the helper twice in branches; manual triage.
  - 2026-05-15: structural guard added — `view_session()` context manager (`src/dashboard/utils/__init__.py`) opens exactly 1 conn + auto-closes; CLAUDE.md #9 now mandates it for new views. Migrated views (instagram, soundcloud) can't regress. Existing un-migrated views keep the legacy manual guard (correct, not the bug) — class stays `open` until coverage is broad.

## naive-datetime-now
- status: open
- severity: P2
- kind: heuristic
- symptom: bare `datetime.now()` persisted to DB / returned from API → host-TZ-naïve, mis-orders vs aware `+00:00` siblings (`.claude/rules/python.md`).
- signature: `! grep -rnE "[^.a-z]datetime\.now\(\)" src/ --include=*.py | grep -viE "strftime|filename|pdf|email"`
- autofix: none
- guard: { type: cross-cutting-rule, ref: .claude/rules/python.md }
- rex_ref: .claude/rules/python.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: catalogued. Heuristic — cosmetic strftime/filename/pdf/email uses are exempt per python.md; the `grep -vi` is a coarse exemption filter, manual triage on hits.

## df-na-rep
- status: guarded
- severity: P3
- kind: heuristic
- symptom: `df.style.format({...})` without `na_rep=` → `TypeError` when a formatted column is NULL (LEFT JOIN / empty window).
- signature: `! grep -rnE "\.style\.format\(" src/dashboard/views/ | grep -v "na_rep"`
- autofix: none
- guard: { type: posttooluse-hook, ref: .claude/hooks/lint_dashboard_view.py }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-05-14 (ref: DEVLOG#2026-05-14)
- History:
  - 2026-05-14: `lint_dashboard_view.py` PostToolUse hook added (warns on save).
  - 2026-05-15: catalogued so `make audit` also sweeps the existing tree (the hook only catches new edits).

## unregistered-write-table
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a table passed as a literal to `upsert_many`/`insert_many` is absent from `_ALLOWED_TABLES` (postgres_handler) → the SQL-injection allowlist raises a cryptic `ValueError` at write time, the DAG fails or silently leaves a data gap.
- signature: `python3 -c "import re,pathlib,sys; ph=pathlib.Path('src/database/postgres_handler.py').read_text(); a=set(re.findall(r\"'([a-z0-9_]+)'\", re.search(r'_ALLOWED_TABLES = frozenset\(\{(.*?)\}\)', ph, re.S).group(1))); bad={m.group(1) for p in pathlib.Path('src').rglob('*.py') for m in re.finditer(r'(?:upsert_many|insert_many)\(\s*[\\'\\\"]([a-z0-9_]+)', p.read_text(errors='ignore'))}-a; sys.exit(1 if bad else 0)"`
- autofix: none
- guard: { type: ci-step, ref: tests/test_allowed_tables_coverage.py }
- rex_ref: .claude/skills/db-schema.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: discovered while adding `instagram_media`/`instagram_media_insights` (plan flagged it as the "highest gotcha"); both registered correctly so 0 live hits. Wired `tests/test_allowed_tables_coverage.py` (blocks via the existing CI pytest job). Canonical signature lives in the test; the inline one-liner above is the catalogue/`make audit` mirror.

## view-session-adoption
- status: open
- severity: P4
- kind: heuristic
- symptom: a view uses raw `get_db_connection()` + the manual `get_artist_id()` guard instead of the `view_session()` context manager. The manual form is correct but not structurally enforced — every copy is a fresh chance to reintroduce `db-connection-per-show` / `artist-id-or-1`. Adoption backlog tracker.
- signature: `! for f in src/dashboard/views/*.py; do grep -q "import get_db_connection" "$f" && ! grep -q view_session "$f" && echo "$f"; done | grep .`
- autofix: none
- guard: { type: cross-cutting-rule, ref: CLAUDE.md#9 }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: `view_session()` shipped + mandated for NEW views (CLAUDE.md #7/#9, dashboard-view skill). 2/32 views migrated (instagram, soundcloud — the clean try/finally shape). 30 remain on the legacy guard (try/except/finally or db-None/require_plan/helper-fn variants — migrating changes behaviour, so deliberately incremental). NOT CI-blocking: 30 valid views would make the gate permanently red (flaky-gate antipattern, cf. rules #6–#10). Status `open` = adoption backlog, not a defect; per-view migration is opt-in maintenance.

## mixed-date-timestamp
- status: guarded
- severity: P2
- kind: heuristic
- symptom: a collection mixes psycopg2 `datetime.date` (raw DATE column) and `pd.Timestamp` (a `pd.to_datetime`'d Series); `sorted()` / `pd.merge` on `date` / any `<`/`==` then raises `TypeError: Cannot compare Timestamp with datetime.date`. Data-dependent — only fires when ≥2 sources contribute and only one was converted.
- signature: `! grep -rnE "sorted\(" src/dashboard/views/ | grep -iE "date|_dates" | grep -v "pd\.to_datetime"`
- autofix: none
- guard: { type: cross-cutting-rule, ref: .claude/skills/dashboard-view.md (Pitfall #5) }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: discovered live in `meta_x_spotify.py` (campaign with BOTH Meta + Spotify-popularity data → `all_dates` mixed types). Fixed commit `d264a5e` (`sorted(pd.to_datetime(all_dates))`). Project-wide sweep: this was the ONLY genuine instance; signature is noisy (matches any `sorted(df[col].unique())` incl. string/int cols — db_health/meta_creatives/imusician/ml_performance are false positives). Durable guard = dashboard-view skill Pitfall #5 (normalize date cols right after fetch_df). Heuristic + report-only — NOT CI/`make audit` (false-positive rate too high; flaky-gate antipattern).

## collector-shipped-dag-not-rerun
- status: open
- severity: P3
- kind: heuristic
- symptom: a new collector method + table ship (migration applied, code volume-mounted) but the owning DAG hasn't re-run since, so the table stays empty and the view shows "no data" — looks like a bug, is actually a stale-schedule. (Instagram `instagram_media`: collector committed 13:52 UTC, DAG last ran 10:00 UTC → 0 rows.)
- signature: `docker exec <pg> psql -U postgres -d spotify_etl -tc "SELECT 'instagram_media' WHERE (SELECT COUNT(*) FROM instagram_media)=0 AND to_regclass('instagram_media') IS NOT NULL;"` (per-table; generalise: table exists + 0 rows while a sibling stats table has recent `MAX(collected_at)`)
- autofix: none
- guard: { type: cross-cutting-rule, ref: dev-docs/error-classes.md (operational runbook) }
- rex_ref: .claude/skills/airflow-dag.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: catalogued from the Instagram "Publications récentes" empty report. NOT a code defect — operational: after shipping a collector method that populates a new table, the owning DAG must be re-triggered (it won't backfill until its next scheduled/manual run). Runbook: trigger the DAG, verify `SELECT COUNT(*) FROM <new_table>` > 0, smoke the view. Report-only (no CI gate — DB-state, not source).

## ingest-time-as-release-date
- status: guarded
- severity: P3
- kind: heuristic
- symptom: an `entity_period_filter`/`EntitySpec` orders "latest release" by `MIN(date_column)` where `date_column` is the ingest timestamp (`collected_at`) → default entity = first one WE collected, not the most recently released; "Depuis dernière release" anchors wrong. SoundCloud default track was visibly the wrong one.
- signature: `! grep -rn -A2 "EntitySpec(" src/dashboard/views/ | grep -B2 "collected_at" | grep -L "release_column"` (narrow: EntitySpec with date_column=collected_at lacking release_column — ~0 false positives; broad `collected_at DESC` greps are NOT this class — that's legit "latest snapshot")
- autofix: none
- guard: { type: cross-cutting-rule, ref: .claude/skills/dashboard-view.md (Pitfall #6) }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: discovered live (SoundCloud default track wrong). Root cause: `entity_period_filter` ordered by `MIN(collected_at)` = first ingest, not upload date. Fixed: SC API `track.created_at` → `soundcloud_tracks_daily.track_created_at` (migration 028) + `EntitySpec.release_column` + `soundcloud.py release_column="track_created_at"`. Sweep: only real instance was SC (fixed); `apple_music.py` is the ACCEPTED proxy (no Apple API created_at, `tracks` name-join rejected as over-reach — documented, not a defect). Durable guard = dashboard-view skill Pitfall #6. Heuristic/report-only — NOT CI/`make audit` (broad collected_at-DESC is legit "latest snapshot" everywhere → flaky-gate antipattern).

## operator-guidance-phantom-or-wrong-auth
- status: guarded
- severity: P3
- kind: heuristic
- symptom: operator-facing text (failure-alert root-cause map, Credentials help UI, setup guides) instructs running a script that does not exist, or describes an auth model the collector does not use (e.g. "renew the Spotify refresh_token" / "YouTube OAuth refresh" when Spotify = client_credentials and YouTube = static API key) → at incident time the operator follows a dead end, the real fix (re-paste a rotated secret / regenerate an API key) is never surfaced, MTTR balloons.
- signature: `! grep -rnE "spotify_auth\.py|youtube_auth\.py|test_youtube_auth|check_api_keys_meta|create_missing_tables|Refresh Token (Spotify|YouTube)|YouTube — OAuth" src/utils/alert_root_cause.py src/dashboard/views/useful_links.py src/dashboard/views/credentials.py .claude/dev-docs/*guide*.md`
- autofix: none
- guard: { type: cross-cutting-rule, ref: dev-docs/error-classes.md (operator-doc-vs-collector-auth invariant) }
- rex_ref: .claude/dev-docs/token-management-bilan.md
- first_seen: 2026-05-15 (ref: DEVLOG#2026-05-15)
- History:
  - 2026-05-15: discovered via the token-management bilan (`credentials.py` exposed dormant Spotify `refresh_token`/`redirect_uri` + YouTube OAuth fields the collectors never read). Explore sweep found the SAME class in `alert_root_cause.py` (Spotify entry pointed at phantom `python src/collectors/spotify_auth.py` "to renew the refresh token" — Spotify has none; YouTube entry said "renew the OAuth Refresh Token" — it's a static API key) and `useful_links.py` (YouTube setup expander built on `credentials.json`/`token.json`/phantom `scripts/test_youtube_auth.py` + "tokens auto-refresh" myth; Spotify expander "relancer le flow d'auth"; "Scripts utilitaires" listed 3 phantom commands: `test_youtube_auth.py`, `check_api_keys_meta.py`, `scripts/create_missing_tables.sql`). Ground truth: Spotify=client_credentials (re-granted each run, NO refresh token); YouTube=static `developerKey` (no OAuth, no expiry); SoundCloud=client_credentials default + opt-in auto-rotating user-token; Meta/IG=System User token (never expires). Real scripts in `scripts/` = only `backup_db.sh`, `manage_mapping.py`, `test_email.py`. All instances fixed this pass (credentials.py field-list/_test_youtube/_guide_*; alert_root_cause.py spotify+youtube entries; useful_links.py YouTube+Spotify expanders + scripts list → `make migrate` + a "no auth script — use the Test button" caption). Durable guard = this catalogue entry + token-management-bilan.md as the canonical per-platform auth model. Heuristic + report-only — NOT CI/`make audit`: the signature would self-match any doc that *quotes* the anti-pattern (the artist-id-or-1 false-positive lesson), so it is deliberately scoped to the 3 operator-facing source files + `*guide*.md` only, and excludes this catalogue + the bilan. Re-run after edits → 0 hits (class cleared).

## object-dtype-numeric-op
- status: guarded
- severity: P3
- kind: heuristic
- symptom: a numeric DB column that contains a NULL loads as pandas `object` dtype; subsequent arithmetic + `Series.round(n)` then raises `TypeError: Expected numeric dtype, got object instead.` at render → the view crashes. Data-dependent — only fires once a row is NULL (LEFT JOIN, empty window, a model that failed to score).
- signature: `! grep -rnE "\)\.round\(" src/dashboard/views/ | grep -v "to_numeric"`
- autofix: none
- guard: { type: posttooluse-hook, ref: tests/test_views_render_smoke.py (AppTest renders every view against the live DB → catches it when a NULL is present) }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-05-29 (ref: DEVLOG#2026-05-29)
- History:
  - 2026-05-29: first hit in `revenue_forecast.py` — `ml_song_predictions.{dw,rr,radio}_probability` can be NULL (a model that fails to score writes None) → object Series → `(ml_df[col]*100).round(1)` raised. Fixed with `pd.to_numeric(errors='coerce')` + `.map(...)`.
  - 2026-06-01: second instance in `soundcloud.py` — a NULL in `likes_count`/`reposts_count`/`comment_count` made the column object → `(_eng / _pc * 100).round(1)` raised. Surfaced by the render-smoke harness against fresh live data. Fixed identically (`pd.to_numeric(errors='coerce')` + `.where(_pc != 0)`). Two independent hits → catalogued. Durable fix: coerce every DB numeric column with `pd.to_numeric(..., errors='coerce')` (then `.fillna(0)` or `.where(...)`) BEFORE any arithmetic / `.round()`. Heuristic + report-only — the signature matches any pre-rounded arithmetic (noisy); the render-smoke harness is the real net.

## tz-aware-naive-mix
- status: guarded
- severity: P3
- kind: heuristic
- symptom: a column of ISO timestamp strings where some carry a tz offset (`+00:00`) and some are naive → `pd.to_datetime(series)` or a Plotly datetime coercion (`px.timeline`, scatter x-axis) raises `ValueError: Cannot mix tz-aware with tz-naive values, at position N`. Data-dependent (only fires when old naive rows and new tz-aware rows coexist). Sibling of `mixed-date-timestamp` (that one mixes `datetime.date` vs `pd.Timestamp`; this one mixes tz-aware vs naive inside one `to_datetime`).
- signature: `! grep -rnE "pd\.to_datetime\(" src/dashboard/views/ | grep -vE "utc=True|errors="`
- autofix: none
- guard: { type: posttooluse-hook, ref: tests/test_views_render_smoke.py }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-06-01 (ref: DEVLOG#2026-06-01)
- History:
  - 2026-06-01: `airflow_kpi.py` `df_runs` `start_date`/`end_date` (Airflow REST ISO strings, mixed offsets across old vs recent runs) → `pd.to_datetime` + `px.timeline` raised "at position 26". Surfaced by the render-smoke harness on fresh live data. Fixed by normalising both columns once at source: `pd.to_datetime(col, utc=True, errors='coerce').dt.tz_localize(None)`. Durable fix: when building a datetime column from heterogeneous string sources, always pass `utc=True` then drop the tz (`.dt.tz_localize(None)`) so every consumer sees uniform naive-UTC. Heuristic + report-only (the grep matches benign `to_datetime` calls). Related: `mixed-date-timestamp`.

## snapshot-fixture-hook-reflow
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a byte-exact golden/snapshot fixture under `tests/fixtures/` is silently reflowed by the `trailing-whitespace` / `end-of-file-fixer` pre-commit hooks → the committed golden no longer matches the producer's real output, so the snapshot test that compares against it fails (or, worse, the golden gets regenerated to match the mangled bytes and the test then passes against wrong data).
- signature: `! { test -d tests/fixtures && ! grep -q "tests/fixtures" .pre-commit-config.yaml; }`
- autofix: none
- guard: { type: pre-commit, ref: .pre-commit-config.yaml (exclude `^tests/fixtures/` on trailing-whitespace + end-of-file-fixer) }
- rex_ref: .pre-commit-config.yaml
- first_seen: 2026-06-01 (ref: DEVLOG#2026-06-01)
- History:
  - 2026-06-01: hit while landing R5's `tests/fixtures/pdf_report_golden.html` (the `render_html` snapshot). The eof/trailing hooks stripped a final newline + trailing spaces that the HTML template legitimately emits → golden ≠ `render_html()` output. Fixed by excluding `^tests/fixtures/` from both hooks (detect-secrets already excluded `tests/fixtures/.*`). Rule: any byte-exact fixture directory must be excluded from reflowing hygiene hooks the moment it is introduced.

## song-name-convention-mismatch
- status: guarded
- severity: P2
- kind: heuristic
- symptom: an exact-match join on a song/track title between a FILENAME-derived table (`s4a_song_timeline`, `ml_song_predictions`, manual-entry tables — they carry `_` because S4A replaces `< > : " / \ | ? *` with `_` in export filenames) and a CSV/API-derived table (`s4a_songs_global`, `tracks`, `track_popularity_history`, `campaign_track_mapping` — they keep the real chars) silently returns 0 rows / empty for every title containing one of those chars. The dashboard shows "—" or imputes a 0 ML feature; no error is raised.
- signature: `! { grep -rnE "track_name *=|track_name\)" src/dashboard --include=*.py | grep -iE "%s|LOWER\(" | grep -viE "translate|canonical_song_sql|REPLACE"; }`
- autofix: none
- guard: { type: cross-cutting-rule, ref: src/utils/track_matching.py — canonical_song()/canonical_song_sql() single-source helper; regression test tests/test_song_canonical.py }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-06-08 (ref: DEVLOG#2026-06-08)
- History:
  - 2026-06-08: discovered live — Vue Globale showed no Listeners/Saves for "Qui a bu le crachoir du saloon ?" because `s4a_songs_global` kept `?` while the timeline-derived selector passed `_`. Same class also silently zeroed the ml_inference Saves/listeners feature for all `?` titles, blanked the PI line (`track_popularity_history`) in Suivi Algorithmes, and excluded `?` tracks from the Meta CPR optimizer join (`campaign_track_mapping`). Fix: write-side normalisation in `parse_songs_global` via `canonical_song()` (+ migration 043 backfilling existing rows incl. `s4a_song_saves_daily`), and query-side `canonical_song_sql()` on the CSV/API side of every cross-convention join (`_tab_algos` PI ×4, `meta_cpr_optimizer`, `router` tracks join ×3). `track_release_reference` was already immune (its `normalize_track_title` strips both `?` and `_`). Heuristic + manual triage — the signature also matches same-convention joins (false positives); the durable guard is to route every cross-convention title join through `canonical_song_sql()`.
