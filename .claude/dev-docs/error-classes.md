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

<!-- fields-ratchet: 25 -->

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
- **Executor**: `.claude/scripts/audit_runner.py` parses this file and runs every
  `signature`. `--deterministic` runs only `kind: deterministic` classes and is a
  **blocking** step in `ci.yml`; `--all` runs everything **non-blocking** nightly
  (`security-nightly.yml`) and via `make audit`. Adding a class here wires it in
  automatically — no hand-edited grep recipe to keep in sync.

## Per-class schema

```
## CLASS-ID
- status:    guarded | reported | open
- severity:  P1 | P2 | P3 | P4        (CLAUDE.md Cross-Cutting Rule #4)
- kind:      deterministic | heuristic
- symptom:   one line — the observed failure
- signature: `<exact shell command, exit!=0 on hit>`
- root_cause: <une ligne, fichier:ligne quand c'est lisible>
- long_term_fix: <le changement qui rend la classe impossible, ou "— (le garde EST le fix)">
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
| [i18n-untranslated-key](#i18n-untranslated-key) | P3 | deterministic | guarded | none |
| [api-router-schema-drift](#api-router-schema-drift) | P3 | heuristic | guarded | none |
| [csv-formula-injection](#csv-formula-injection) | P3 | heuristic | guarded | none |
| [config-not-env](#config-not-env) | P2 | heuristic | guarded | none |
| [prod-canonical-schema-drift](#prod-canonical-schema-drift) | P2 | manual | reported | none |
| [multitenant-dag-fleet-poisoning](#multitenant-dag-fleet-poisoning) | P2 | deterministic | guarded | none |
| [collector-import-dotenv-crash](#collector-import-dotenv-crash) | P2 | deterministic | guarded | none |
| [env-not-wired-to-service](#env-not-wired-to-service) | P1 | deterministic | guarded | none |
| [prod-compose-drift](#prod-compose-drift) | P2 | heuristic | reported | none |
| [central-app-missing](#central-app-missing) | P2 | manual | reported | none |
| [multitenant-mono-test-blindspot](#multitenant-mono-test-blindspot) | P2 | manual | reported | none |
| [config-path-dangling](#config-path-dangling) | P2 | deterministic | guarded | none |
| [config-status-file-unrendered](#config-status-file-unrendered) | P2 | deterministic | guarded | none |
| [trigger-threshold-split](#trigger-threshold-split) | P3 | deterministic | guarded | none |
| [rex-delimiter-unanchored](#rex-delimiter-unanchored) | P3 | deterministic | guarded | none |
| [connection-test-proves-app-not-tenant](#connection-test-proves-app-not-tenant) | P2 | deterministic | guarded | none |
| [identity-read-but-never-collectable](#identity-read-but-never-collectable) | P2 | deterministic | guarded | none |
| [guide-single-os-shortcut](#guide-single-os-shortcut) | P3 | deterministic | guarded | none |
| [first-paint-chart-overload](#first-paint-chart-overload) | P3 | deterministic | guarded | none |
| [tenant-identity-falls-back-to-admin](#tenant-identity-falls-back-to-admin) | P1 | deterministic | guarded | none |
| [write-without-explicit-artist-id](#write-without-explicit-artist-id) | P1 | deterministic | guarded | none |
| [upsert-transfers-row-ownership](#upsert-transfers-row-ownership) | P1 | deterministic | guarded | none |
| [dag-trigger-without-tenant-scope](#dag-trigger-without-tenant-scope) | P1 | deterministic | guarded | none |
| [ast-guard-blind-to-bom](#ast-guard-blind-to-bom) | P2 | deterministic | guarded | safe |
| [migration-ahead-of-its-code](#migration-ahead-of-its-code) | P1 | manual | reported | none |
| [column-name-is-not-its-meaning](#column-name-is-not-its-meaning) | P2 | deterministic | guarded | none |
| [identity-claimed-by-two-tenants](#identity-claimed-by-two-tenants) | P2 | deterministic | guarded | none |
| [probe-scoped-to-the-machine-not-the-repo](#probe-scoped-to-the-machine-not-the-repo) | P3 | deterministic | guarded | none |
| [state-path-namespaced-by-another-project](#state-path-namespaced-by-another-project) | P3 | deterministic | guarded | none |

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
- kind: deterministic
- symptom: a collector `except` block logs then returns empty (`None`/`[]`/`{}`) → DAG upserts 0 rows, exits SUCCESS, no alert, dashboard silently stale.
- signature: `python3 .claude/scripts/audit_collectors_ast.py`
- autofix: none
- guard: { type: ci-step, ref: .claude/scripts/audit_collectors_ast.py via audit_runner.py --deterministic (ci.yml) }
- rex_ref: .claude/skills/audit-collectors.md
- first_seen: 2026-03-25 (ref: DEVLOG#2026-03-25)
- History:
  - 2026-03-25: 8 files audited + fixed (see audit-collectors.md table).
  - 2026-05-15: catalogued. Fix guidance stays in audit-collectors.md (rules 1–4); this entry is the machine-detectable index only.
  - 2026-05-15: regression — `youtube_collector.get_video_comments` (l.242) + `get_playlists` (l.296) caught `except Exception`, logged, then `return comments`/`return playlists` (partial collection). Missed by the 2026-03-25 sweep (only get_channel_stats/videos/video_stats were fixed; the audit-collectors.md status table over-claimed YouTube fully done). Both → `raise`. Note: `get_channel_stats:43-45` / `get_channel_videos:93-95` `return None`/`return videos` on a *successful* empty-`items` response are a distinct case (not an `except` block) — left for a dedicated pass.
  - 2026-05-15: re-sweep post-fix. AST scan ("any non-raising `return` inside an `except` in `src/collectors/*.py`") = the precise detector — confirms youtube l.242/296 now raise project-wide; **0 real instances remain**. The catalogued grep signature is confirmed `heuristic`: noisy (11 hits, ~all legit success-path `return data`/`return tracks`) AND was blind to the partial-return variant (`return comments`/`return playlists`) — the AST scan supersedes it as the re-verification tool (signature line kept append-only; not rewritten — guard is the PostToolUse hook + audit-collectors skill, not this grep). Accepted false-positive: `instagram_api_collector.py:105` `return False` in `except` of `_refresh_access_token()` — a bool-STATUS helper (contract IS bool; `_check_proactive_refresh` calls it best-effort, no upsert depends on it), NOT the data class. Documented FP shape: bool/None-status helpers vs data-returning fetch methods. Class stays `guarded`.
  - 2026-06-13: the AST scan the 2026-05-15 entry called "the precise detector" now EXISTS as `.claude/scripts/audit_collectors_ast.py` (flags any non-raising return inside an except in `src/collectors/*.py`; `return True/False` excluded as the documented bool-status FP). It replaces the noisy grep as the catalogue `signature` and runs **blocking** in CI via `audit_runner.py --deterministic` (0 hits today). kind heuristic→deterministic — the #1 recurring class (9 REX entries) can no longer merge.

## artist-id-or-1
- status: guarded
- severity: P1
- kind: deterministic
- symptom: `get_artist_id() or 1` coerces an unhydrated session onto artist 1 → cross-tenant data leak (CLAUDE.md rule #7).
- signature: `! grep -rnE "=[[:space:]]*get_artist_id\(\)[[:space:]]+or[[:space:]]+1" src/`
- autofix: none
- guard: { type: ci-step, ref: .claude/scripts/audit_runner.py --deterministic (ci.yml) }
- rex_ref: CLAUDE.md
- first_seen: 2026-03-27 (ref: DEVLOG#2026-03-27)
- History:
  - 2026-03-27: 9 views fixed with explicit guard. Pattern still ungrepped in CI until now.
  - 2026-05-15: catalogued, added to `make audit`.
  - 2026-05-15: no-arg /sweep caught a FALSE POSITIVE — the prior signature `get_artist_id() *or *1` matched the `view_session()` docstring + CLAUDE.md rule text that *quote* the anti-pattern, breaking the `deterministic` (CI-safe) contract. Hardened to require assignment context `= get_artist_id() or 1` (verified 0 real hits, docstring excluded). `make audit` recipe synced to the same regex (no catalogue↔audit drift).
  - 2026-06-13: **now CI-BLOCKING** — `audit_runner.py --deterministic` runs every `kind: deterministic` signature as a blocking ci.yml step (0 real hits today). status open→guarded; this P1 leak pattern can no longer merge.

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
  - 2026-06-10: 2 new tables (`s4a_song_nonalgo_streams`, `s4a_artist_radio_count`, migration 052) registered correctly. A user-facing crash DID occur (`Saisie S4A` save raised the guard) but the root cause was a STALE running streamlit process (pre-fix code in memory), not a missing entry — the allowlist was already updated in the committed code. REX: a redundant guard (`tests/test_db_table_allowlist.py`) was added then **consolidated** back into `test_allowed_tables_coverage.py` (which now also scans `"table": "name"` config dicts, e.g. upload_csv._PLATFORMS) — grep existing coverage / this catalogue BEFORE adding a new guard.

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

## i18n-untranslated-key
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a `t("ns.key", "FR …")` / `_t("ns.key", "FR …")` call has no EN entry in `i18n_catalog/` → EN mode silently renders the French default (untranslated surface), no error.
- signature: `python3 -m pytest tests/test_i18n.py::test_every_static_t_key_has_en_entry -q`
- autofix: none
- guard: { type: ci-step, ref: tests/test_i18n.py::test_every_static_t_key_has_en_entry }
- rex_ref: tests/test_i18n.py
- first_seen: 2026-06-10 (ref: DEVLOG#2026-06-10)
- History:
  - 2026-06-10: added during the full i18n sweep (~2300 keys). The pre-existing guard only covered nav (`test_every_nav_item_key_has_en`); the new whole-codebase guard scans every literal namespaced `t(`/`_t(` call across `src/dashboard/` (word-boundary excludes `.get(`/`.getenv(`; dynamic f-string keys skipped) and asserts each resolves in `_TR['en']`. Locks in EN coverage incl. the bilingual PDF (`_t("pdf.…")`).

## api-router-schema-drift
- status: guarded
- severity: P3
- kind: heuristic
- symptom: a FastAPI data router (Brick-14) SELECTs a column renamed/dropped by a later migration → the endpoint 500s for every tenant (no client stack-trace leak, but fully broken). The mocked `test_api.py` cannot see it because the DB is a MagicMock.
- signature: `python3 -m pytest tests/test_api_db_smoke.py -q` (DB-gated: runs every data endpoint against the real schema with a forged admin+tenant token, asserts no 500; skips cleanly with no provisioned Postgres)
- autofix: none
- guard: { type: ci-step, ref: tests/test_api_db_smoke.py }
- rex_ref: .claude/commands/review-db-schema.md
- first_seen: 2026-06-13 (ref: DEVLOG#2026-06-13-suite18)
- History:
  - 2026-06-13: `/kpis` (`youtube_video_stats.views`→`view_count`, `ml_song_predictions.score` dropped→`dw_probability`) found+fixed (suite 18). `/youtube/videos` (`views/likes/comments/title` on `youtube_video_stats`, real cols `view_count/like_count/comment_count` + no `title` → query `youtube_videos`) found+fixed (suite 19b). Both escaped the mocked suite → DB-gated `test_api_db_smoke.py` added as the guard for the whole class. Durable lesson: a column migration must grep ALL consumers incl. `src/api/routers/`, not just dashboard views (rex in review-db-schema).

## csv-formula-injection
- status: guarded
- severity: P3
- kind: heuristic
- symptom: user-controlled values (song/campaign names, usernames) exported via `to_csv`/`to_excel` without defang → a cell like `=cmd|'/c calc'!A1` executes when the victim opens the file in Excel/Sheets (CWE-1236); worst case the admin multi-tenant export.
- signature: `! grep -rnE 'to_(csv|excel)\(' src/dashboard --include=*.py | grep -viE 'defang_formulas|#'`
- autofix: none
- guard: { type: cross-cutting-rule, ref: src/dashboard/utils/csv_exporter.py (defang_formulas) }
- rex_ref: —
- first_seen: 2026-06-13 (ref: DEVLOG#2026-06-13-suite20)
- History:
  - 2026-06-13: found via dashboard red-team — `export_all` (csv), `export_excel` (xlsx) and the admin opt-in export (`admin.py`) wrote raw values. Fix: `defang_formulas()` prefixes any string cell starting with `=,+,-,@,\t,\r` with `'` (OWASP), applied to all 3 export paths + guard test `test_defang_formulas_neutralizes_injection`. Durable rule: every new `to_csv`/`to_excel` export of DB/user data must route through `defang_formulas()`.

## config-not-env
- status: guarded
- severity: P2
- kind: heuristic
- symptom: a bootstrap/runtime path subscripts `config['…']` directly (config.yaml-only) instead of reading env first → `KeyError` in prod where there is no `config.yaml` (SMTP, DATABASE_URL, FERNET_KEY, Airflow URL, DB schema bootstraps). 4 REX recurrences; this session fixed 11 `*_schema.py` bootstraps.
- signature: `! grep -rnE "config(_loader\.load\(\))?\[" src/database/*_schema.py`
- autofix: none
- guard: { type: cross-cutting-rule, ref: .claude/skills/dashboard-view.md (pitfall: config env-fallback) }
- rex_ref: .claude/skills/dashboard-view.md
- first_seen: 2026-06-13 (ref: DEVLOG#2026-06-13-suite15)
- History:
  - 2026-06-13: the 11 `src/database/*_schema.py` `__main__` bootstraps did `PostgresHandler(**config['database'])` → `KeyError` when launched in prod (no config.yaml; `config_loader.load()` returns `{}`). Fixed via `PostgresHandler.from_env_or_config()` (env DATABASE_URL → config.yaml → explicit RuntimeError). Catalogued **scoped to `*_schema.py`** (0 hits today) to flag regressions; kept `heuristic`/nightly — a project-wide `config[` sweep false-positives on the dashboard, which reads config.yaml *by design* (CLAUDE.md). The narrow scope IS the precision.

## prod-canonical-schema-drift
- status: reported
- severity: P2
- kind: manual
- symptom: the live prod DB has a table/column the version-controlled schema (`init_db.sql` + `migrations/*.sql`) lacks, or vice-versa. Code reading/writing the drifted column works in prod but 500s on a fresh install / in CI (e.g. `youtube_videos.view_count`). Cause: a manual `ALTER` on prod, an old schema version never migrated, or a migration never applied to prod.
- signature: `make schema-check PROD_SSH=user@host`
- autofix: none
- guard: { type: make-precondition, ref: tools/dev/schema_drift_check.py via `make schema-check` }
- rex_ref: tools/dev/schema_drift_check.py
- first_seen: 2026-06-13 (ref: DEVLOG#2026-06-13-suite23)
- History:
  - 2026-06-13: surfaced by the `/youtube/videos` 500 — prod `youtube_videos` carried orphan `view/like/comment_count` (manual ALTER) absent from canonical. `make schema-check` (provisions a throwaway canonical from init_db.sql+migrations, diffs vs prod `information_schema`) found **7 drifted tables**: USED-but-undeclared (`etl_daily_metrics`, `apple_songs_performance.{purchases,radio_spins,shazam_count}`, `meta_adsets.age_range` → reconcile into canonical) + orphan prod-extra (`meta_spotify_mapping`, `meta_ads.video_file_name`, `meta_adsets.targeting_optimization`, `youtube_videos.{view,like,comment}_count` → drop/document) + prod-missing PKs (`youtube_channels.id`, `youtube_videos.id`). `kind: manual` — needs prod SSH, not run by audit_runner/CI; the durable rule is **schema changes via migrations only, never a manual ALTER on prod** (prod = init_db.sql + migrations by construction). Full triage: `.claude/dev-docs/schema-drift-2026-06-13.md`.

## multitenant-dag-fleet-poisoning
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a collector/processing DAG iterates `get_active_artists()` and a per-tenant `raise` (or a precheck that raises on ANY incomplete artist) is NOT caught per-iteration → ONE bad tenant fails the whole DAG for ALL tenants. Benken's empty YouTube channel (404) failed `youtube_daily` for everyone; soundcloud/instagram prechecks raised on his missing creds.
- signature: `python3 -m pytest tests/test_dag_fleet_isolation.py -q`
- autofix: none
- guard: { type: test, ref: tests/test_dag_fleet_isolation.py (every artist loop touching `db` must be try-wrapped) }
- rex_ref: .claude/skills/airflow-dag.md
- first_seen: 2026-06-19 (ref: Benken onboarding incident)
- History:
  - 2026-08-20: two live instances found on the same day, both invisible to the parity test because they live in prod's untracked copy. (1) `SPOTIFY_ARTIST_IDS` and `META_AD_ACCOUNT_ID` were declared with the ADMIN's identity HARDCODED as the compose default (`${VAR:-7sbfafb…}`), so commenting them out of prod's `.env` changed nothing — the default kept feeding the fallback. (2) The `SMTP_*` block existed only under the `dashboard` service, so the scheduler could send no alert at all. Both fixed in prod and in the example. The lesson: a `${VAR:-default}` in compose is a value, not a placeholder — an identity must never be one.
  - 2026-06-19: found via the Benken onboarding cascade. Fixed 5 collector DAGs (youtube/soundcloud/instagram/spotify/meta) + 5 more sites found by the impact sweep (spotify collect_top_tracks, ml_scoring_daily, ml_outcome_labeling, weekly_digest, alert_monitor) — per-tenant try/except-continue, fail only if EVERY tenant failed; prechecks softened. Durable rule: a per-tenant loop that touches `db` MUST be wrapped (PR #87/#89).

## collector-import-dotenv-crash
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a module-level `load_dotenv()` in a collector (not wrapped in try/except) raises `PermissionError` at import when the mounted `/opt/airflow/.env` is root-owned 600 (unreadable by the airflow uid 50000) → the collector crashes the moment a DAG imports it. The env is already injected by compose, so reading `.env` is redundant but fatal.
- signature: `python3 -m pytest tests/test_collectors_dotenv_guarded.py -q`
- autofix: none
- guard: { type: test, ref: tests/test_collectors_dotenv_guarded.py (no unguarded module-level load_dotenv in src/collectors) }
- rex_ref: .claude/skills/audit-collectors.md
- first_seen: 2026-06-19 (ref: Benken onboarding incident)
- History:
  - 2026-06-19: unmasked when the soundcloud precheck fix let the collect task reach import. `soundcloud_api_collector.py` + `instagram_api_collector.py` both crashed at import. Fix: wrap `load_dotenv()` in `try/except OSError` (no-op on unreadable .env). PR #88/#89.

## env-not-wired-to-service
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a service's CODE reads a central-app env var (`os.getenv('SOUNDCLOUD_CLIENT_ID')` …) that the service's `docker-compose` block does NOT declare → empty in that container. A silent `''` default hides it. The dashboard ran the credential connection tests but was deployed WITHOUT the central-app env, so EVERY test failed (the Benken incident); SoundCloud was wired to no service at all.
- root_cause: `os.getenv('X')` returns `None`/`''` when the variable is absent, so a container missing an env var behaves like one holding an empty value — no exception, no log, no difference at the call site. The declaration lives in a different file (`docker-compose`) from the read (`src/…`), and nothing joined the two.
- long_term_fix: `tests/test_env_contract.py` joins them — for each service group, every CRITICAL env var read in that group's code must appear in that service's `environment:` block. Two extensions after it missed real cases: the CRITICAL set now includes the ALERTING vars (`SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL`), and the scan follows TRANSITIVE reads — `src/utils` is scanned for both groups, because a DAG that imports `email_alerts` reads env there and the guard was only looking at `airflow/dags` + `src/collectors`.
- signature: `python3 -m pytest tests/test_env_contract.py -q`
- autofix: none
- guard: { type: test, ref: tests/test_env_contract.py (code-reads ⊆ service-declares, per service group, transitive) }
- rex_ref: docs/adr/ADR-006-central-credential-model.md
- first_seen: 2026-06-19 (ref: Benken onboarding incident)
- History:
  - 2026-06-19: the prod (untracked) compose dashboard service omitted SPOTIFY/YOUTUBE/SOUNDCLOUD/META env; SoundCloud was in no service. Fix: wired the central-app block into the dashboard service of `docker-compose.example.yml` + the SoundCloud vars into the airflow anchor; guard test cross-checks code reads vs the service env block. PR #87/#91.

## prod-compose-drift
- status: reported
- severity: P2
- kind: heuristic
- symptom: the live prod `docker-compose.yml` is UNTRACKED (gitignored) and hand-derived, so it silently diverges from the canonical `docker-compose.example.yml` — a service or env var present in the template is missing on prod (or vice-versa). No test sees it; surfaces only when a user hits the gap. Root structural cause of `env-not-wired-to-service`.
- root_cause: the file that actually runs production is gitignored — it holds secrets, so it cannot be tracked — and the tracked `docker-compose.example.yml` is only a template someone copies once. Nothing compares the two afterwards, and the divergence is invisible from either side: CI reads the example, prod reads its own copy, and no test can reach both at the same time.
- long_term_fix: parity is asserted on the two things a test CAN see — `tests/test_compose_parity.py` (every `${VAR}` of the example is documented in `.env.example`, all services present) and `tests/test_env_contract.py` (code reading an env var ⊆ the service block that declares it, transitive reads included since 2026-08-20). What no local test can see — prod's own copy — is read by `tools/prod_introspect.sh` (SET/MISSING per container) and must be run when a variable is added.
- signature: `python3 -m pytest tests/test_compose_parity.py tests/test_env_contract.py -q`
- autofix: none
- guard: { type: test, ref: tests/test_compose_parity.py + tests/test_env_contract.py + prod-side parity check in tools/prod_introspect.sh }
- rex_ref: docs/adr/ADR-006-central-credential-model.md
- first_seen: 2026-06-19 (ref: Benken onboarding incident)
- History:
  - 2026-06-19: the prod compose drifted from the example (dashboard env, SoundCloud). The example is the only tracked artifact; CI can't diff the untracked prod file. Mitigation: a parity test on the example + `tools/prod_introspect.sh` env-presence probe to catch prod drift manually. Durable rule: never hand-edit prod compose without mirroring the example.

## central-app-missing
- status: reported
- severity: P2
- kind: manual
- symptom: a shared central-app credential (SPOTIFY_CLIENT_ID/SECRET, YOUTUBE_API_KEY, SOUNDCLOUD_CLIENT_ID/SECRET, META_ACCESS_TOKEN) is absent or expired in prod → every tenant's connection test + collection for that platform fails at once, but nothing detects it until a user hits it.
- root_cause: the central-app model (ADR-006) concentrates one credential per platform for the whole fleet, so a single absent variable is a fleet-wide outage — and it is read with `os.getenv(name, '')`, whose empty default makes absence indistinguishable from a wrong value at the call site. Nothing probed the apps themselves; the first detector was a human failing to connect.
- long_term_fix: probe every central app BEFORE a tenant does — `tools/check_central_apps.py`, now step 1 of `make artist-preflight`. Its `--require` flag (2026-08-20) makes an ABSENT app red: the default mode skipped an unconfigured platform and still exited 0, which is exactly how "all the credentials failed" reached a beta artist. The env→service wiring itself is guarded by `tests/test_env_contract.py`.
- signature: `python3 tools/check_central_apps.py --require`
- autofix: none
- guard: { type: ops-probe, ref: tools/check_central_apps.py (authenticates each shared app; exit 1 if a configured app fails) }
- rex_ref: docs/adr/ADR-006-central-credential-model.md
- first_seen: 2026-06-19 (ref: Benken onboarding incident)
- History:
  - 2026-06-19: SoundCloud central app was unprovisioned in prod ("app non configurée → contacter admin"). The model needs the admin to provision + rotate one app per platform. `tools/check_central_apps.py` probes each before a tenant hits it; run pre-onboarding-session.
  - 2026-08-20: the probe existed but was never run before a session, and its skip-on-absent behaviour meant it would have exited 0 anyway. Wired into `make artist-preflight` as step 1, with `--require`. Adjacent instance found the same day: `SMTP_*`/`ALERT_EMAIL` were declared only for the `dashboard` service, so the Airflow scheduler could send no alert at all — 672 CSV-watcher failures over a week went unreported. Same class, different variable; `test_env_contract` was extended to TRANSITIVE reads (`src/utils`), which was its blind spot.

## multitenant-mono-test-blindspot
- status: reported
- severity: P2
- kind: manual
- symptom: every smoke/integration test runs with `artist_id=1` only → a bug that appears only for tenant #2 (per-tenant SQL scoping, NULL handling, missing identity, fleet-poisoning) ships green. The whole Benken incident class was invisible because nothing exercised a second/new tenant.
- root_cause: artist 1 is the admin — the tenant with years of data, every identity declared, and (as admin) no SQL scoping applied at all. It is the single configuration in which a tenant bug CANNOT appear, and it was the only one under test. Worse, the suite only ever exercised the READ path: `test_tenant_isolation.py` tests the SQL filter, nothing tested which tenant a row is written under.
- long_term_fix: two tenants, and the write path. `tests/test_e2e_two_tenants.py` runs the real DAG collection functions with the platform HTTP layer stubbed so the response DEPENDS on the identity requested — a row of A under B's `artist_id` is then directly observable. `test_views_render_smoke.py` gained a non-admin pass over an empty tenant (the day-one state), and `test_signup_funnel_db.py` covers account creation. Proven: 7 red on the pre-fix tree, 9 green after.
- autofix: none
- guard: { type: cross-cutting-rule, ref: extend tests/test_api_db_smoke.py + tests/test_views_render_smoke.py to ≥2 tenants }
- rex_ref: docs/adr/ADR-006-central-credential-model.md
- first_seen: 2026-06-19 (ref: Benken onboarding incident)
- History:
  - 2026-06-19: confirmed by audit — render-smoke + api-db-smoke both use artist_id=1. Durable rule: new tenant-scoped views/endpoints must be smoke-tested for a sparse 2nd tenant, not just artist 1.
  - 2026-08-20: the rule was written and never implemented; a second beta session failed the same way. Closed with the two-tenant E2E above. The blind spot cost two artist sessions — the interval between naming a guard and building it is where the class lives.

## config-path-dangling
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a rule, skill or command names a `.claude/` file that is not there. Nothing errors — the instruction is simply unfollowable, and the reader cannot tell an absent file from an unimportant one.
- signature: `python3 .claude/scripts/check_config_refs.py`
- root_cause: a path in configuration is prose to every tool that reads it; only the model resolves it, at read time, and it has no way to report the miss. `.claude/scripts/check_config_refs.py`
- long_term_fix: resolve every `.claude/` path against the disk in CI — `tests/test_claude_config_floor.py::test_every_claude_path_named_in_configuration_resolves`. A path that stops resolving now fails a build instead of degrading a session silently.
- autofix: none
- guard: { type: ci-step, ref: tests/test_claude_config_floor.py::test_every_claude_path_named_in_configuration_resolves + ci.yml }
- rex_ref: .claude/commands/resume.md
- first_seen: 2026-07-28 (ref: five dead references found in the deployment channel itself)
- History:
  - 2026-07-28: guard written; found 5 dead references, incl. a mandatory CLAUDE.md instruction naming a file absent on three repos.
  - 2026-08-03: signature seen RED on an injected dangling path in `commands/sprint.md` and GREEN after removal. Promoted from hand-run to a pytest case + a blocking ci.yml step — it had been green only because someone remembered to type it. REX-block lines are exempt: naming the path that broke IS the lesson (same exemption `--prose` grants).

## config-status-file-unrendered
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a file the tooling treats as the status source is an un-expanded bootstrap template — literal `$(date +%Y-%m-%d)`, `TODO: fill in` — so every reader of it reports a clean state that was never measured.
- root_cause: the path resolves, so a path-existence guard passes. Existence was checked; content was not. `.claude/dev-docs/ROADMAP.md` (deleted 2026-08-03)
- long_term_fix: the status files carry a measured item floor — `tests/test_roadmap_two_files.py`. A template state has zero items and fails it, so "resolves" can no longer be mistaken for "carries anything".
- signature: `python3 -m pytest tests/test_roadmap_two_files.py -q`
- autofix: none
- guard: { type: ci-step, ref: tests/test_roadmap_two_files.py }
- rex_ref: .claude/agents/roadmap-keeper.md
- first_seen: 2026-08-03 (ref: roadmap-two-files-2026-08-03)
- secondary_signature (heuristic, nightly): `! grep -rlE "TODO: (Run|run|fill)" .claude/dev-docs/ .claude/commands/ .claude/agents/`
- History:
  - 2026-08-21: the class was guarded only where it was first found (the roadmap). `/review-architecture` was still reading `.claude/dev-docs/architecture/macro_architecture.md` and `architecture/database_schema.md` — both still carrying "TODO: Run generate-dev-docs.py" — while the populated architecture doc lives at `.claude/dev-docs/architecture.md`. The command therefore compared the codebase against two empty files and could not produce a true statement; rewritten. Running `tools/generate-dev-docs.py` populated `api/endpoints.md` (8 routes) and `architecture/database_schema.md` (47 tables, 536 column TODOs left for an agent) but not `macro_architecture.md` (its module/service extractors find 0 here). The remaining question — populate the `architecture/` tree or retire it in favour of `architecture.md` — is a decision, not a defect, and is tracked as R34. The heuristic signature above makes any future unrendered template visible in `make audit` instead of waiting to be read by a command.
  - 2026-08-03: found while verifying rule 17. Eleven config surfaces (`/adr`, `/resume`, `/sprint`, `/dev-docs`, `strategic-plan-architect`, `check_roadmap_update.py`, `session_summary.py`, `bug-resolution.md`, `verification/`, `engineering-loop.js`, rule 17) named a template nothing had ever written, while the real 891-line roadmap sat elsewhere. Two hooks watched its mtime, so their freshness reminder was permanently true and therefore carried no information. Template deleted, surfaces repointed to the two-file roadmap. Signature seen RED with the template restored in place of the active file, GREEN after.

## trigger-threshold-split
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a rule, the agent it spawns, and the hook that signals it state different thresholds. The agent's `description` wins, because it is the only one the router reads — so the effective trigger is the one no other surface agrees with.
- root_cause: the threshold was written three times in three files with nothing comparing them; the agent description also cited "CLAUDE.md rule 1", which resolves to an unrelated rule. `.claude/agents/build-error-resolver.md`
- long_term_fix: a test parses the number out of all three surfaces and fails unless they are equal — `tests/test_claude_config_floor.py::test_the_build_error_threshold_agrees_across_its_three_surfaces`. Changing the threshold stays easy; changing it in one place stops being possible.
- signature: `python3 -m pytest tests/test_claude_config_floor.py::test_the_build_error_threshold_agrees_across_its_three_surfaces -q`
- autofix: none
- guard: { type: ci-step, ref: tests/test_claude_config_floor.py }
- rex_ref: .claude/agents/build-error-resolver.md
- first_seen: 2026-08-03 (ref: roadmap-two-files-2026-08-03)
- History:
  - 2026-08-03: CLAUDE.md rule 12 said ≥5, the agent description said ≥1, `session_summary.py:189` fired at 5. Aligned on 5 — the only value anything actually emits. Signature seen RED with the description desynced to ≥1, GREEN after.

## rex-delimiter-unanchored
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a validator reports a tool as carrying no `rex:` block when the block is present and correct — it could not parse, and said "absent". The reader is sent to add something that is already there.
- root_cause: `_DOCSTRING_FM_RE` matched an unanchored `---\n`, so an RST section underline (a line of dashes) opened a false frontmatter block and the prose after it went to `yaml.safe_load`. `.claude/scripts/validate_rex.py:66`
- long_term_fix: the delimiter is anchored to a line that is exactly `---` (`^...$`, MULTILINE), and a unit test feeds the parser a docstring with RST underlines — `tests/test_claude_config_floor.py::test_the_rex_parser_survives_rst_underlines`. The wider lesson is in the message: a parser must not report absence when it means "I could not read".
- signature: `python3 -m pytest tests/test_claude_config_floor.py::test_the_rex_parser_survives_rst_underlines -q`
- autofix: none
- guard: { type: ci-step, ref: tests/test_claude_config_floor.py + validate_rex.py --strict in ci.yml }
- rex_ref: .claude/scripts/validate_rex.py
- first_seen: 2026-08-03 (ref: roadmap-two-files-2026-08-03)
- History:
  - 2026-08-03: `--strict` exited 1 on `scripts/select_tests.py`, whose `rex: []` was valid — it would have failed CI on this branch. Repo-wide sweep of every `.claude/**/*.py`: 1 file affected today, but the class is live for any future docstring using RST underlines. Signature seen RED on the old regex, GREEN on the anchored one.

## ci-runs-twice-for-one-commit
- status:    guarded
- kind:      deterministic
- signature: `bash -c '! python3 .claude/scripts/check_ci_waste.py 2>/dev/null | grep -q "ci-runs-twice-for-one-commit"'`
- root_cause: `.github/workflows/ci.yml` déclarait `push: branches: ["**"]` ET `pull_request:`. Les deux événements se déclenchent sur le même commit dès qu'une PR est ouverte, et le workflow tourne intégralement deux fois — même arbre, même SHA, même résultat. Le second run ne peut, par construction, rien apprendre que le premier n'ait déjà dit. Mesuré le 2026-08-17 sur les 20 derniers runs de `ci.yml` : **15 SHA distincts pour 20 runs**, dont 5 commits portant à la fois un run `push` et un run `pull_request`, à ~2 min 40 pièce. Le défaut était invisible parce que les deux runs étaient VERTS : un test qui échoue se voit, un run qui coûte le double ne se voit pas.
- long_term_fix: `push` restreint à `[main, dev]`, `pull_request` conservé, `workflow_dispatch` ajouté pour relancer une branche sans PR à la main. Conséquence assumée : une branche SANS PR ouverte ne déclenche plus la CI sur push — ouvrir la PR (même en brouillon) rétablit la porte.
- guard:     `.claude/scripts/check_ci_waste.py` (règle 1), appelé en CI à l'étape des gardes déterministes.
- history:   2026-08-17 — signature vue **rouge** sur `HEAD` (worktree détaché) et **verte** après restriction du déclencheur.

## ci-has-no-concurrency-group
- status:    guarded
- kind:      deterministic
- signature: `bash -c '! python3 .claude/scripts/check_ci_waste.py 2>/dev/null | grep -q "ci-has-no-concurrency-group"'`
- root_cause: aucun bloc `concurrency:` sur un workflow d'itération. Trois poussées rapprochées mettaient trois runs complets en file et les laissaient tous aller au bout, alors qu'un seul peut encore être vrai — les deux premiers valident un arbre que l'auteur a déjà remplacé. `msdr` portait ce groupe depuis son premier jour ; ce dépôt non. La flotte partage une configuration Claude, elle ne partage pas ses workflows : ce qui est appris d'un côté ne traverse pas tout seul.
- long_term_fix: `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`. Le garde ne l'exige que des workflows d'ITÉRATION — ceux qui portent un `pull_request` ou un `push` à joker. Un workflow de release déclenché par `push: [main]` n'est pas concerné : l'annuler à mi-chemin est une perte, pas une économie, et un garde qui prescrit une régression n'est pas un garde.
- guard:     `.claude/scripts/check_ci_waste.py` (règle 2).
- history:   2026-08-17 — vue rouge sur `HEAD`, verte après ajout du groupe. Le premier jet du garde signalait aussi `cd-release.yml` ; la règle a été resserrée et la cellule qui l'aurait attrapé est au `--self-test`.

## connection-test-proves-app-not-tenant
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a "Test the connection" button validates the **platform's shared admin app** (Spotify client_credentials, YouTube API key, Meta `/me`, SoundCloud OAuth token) and returns ✅ without ever exercising the tenant's own identifier — or returns ✅ on an empty result set. The artist reads "Connecté", the DAG upserts 0 rows and exits SUCCESS, the view stays empty for a day. It is `collector-silent-success` moved one layer up, into the form, where it is worse: the artist has been told it works.
- root_cause: the shared-app (central credential) model made the app credentials env-owned, so the tests were written against the only thing that was always present — the app — and the per-artist identifier stayed optional in the test path even though the collector cannot run without it.
- signature: `python3 -m pytest tests/test_connection_test_proves_tenant.py -q`
- long_term_fix: every `CONNECTION_TESTS[platform]` must probe the artist's own asset (`/act_<id>`, `channels?id=`, `/users/<id>/tracks`, `/artists/<id>`) and treat an empty result as a failure with the next action named. A missing tenant identifier is `False`, never `True`.
- autofix: none
- guard: { type: test, ref: tests/test_connection_test_proves_tenant.py }
- rex_ref: src/dashboard/views/credentials/_registry.py
- first_seen: 2026-06-15 (Benken — Meta ad account never shared, YouTube channel empty)
- History:
  - 2026-06-15: first instance (Benken). Treated as a per-artist data gap; closed downstream with `artist_readiness` (a 🔴 status *after* collection), not upstream in the form.
  - 2026-08-12: recurrence, beta session Grinch — SoundCloud "correctement configuré", zero data. `_test_soundcloud` returned ✅ with `count=0`. Sibling sweep found the class on all four platforms: soundcloud (green on 0 tracks), meta (`/me` is identical for every tenant, never touched `account_id`), youtube (key-only green), spotify (green with no artist ID).
  - 2026-08-20: all four fixed + guard added (proven red on the pre-fix tree, green after). Meta now probes `act_<id>` and names asset-sharing as the likely cause; YouTube rejects an empty channel and points at the "… - Topic" channel; SoundCloud rejects a profile with no public track.

## identity-read-but-never-collectable
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a consumer (DAG tenant filter, readiness matrix, collector) reads an identity key from `artist_credentials.extra_config` that **no credential form field ever writes**. The platform is permanently ⚪ "À connecter" with no path to connect it, and the error message may even point at the non-existent field.
- root_cause: consumer and form evolved separately — `instagram_daily` was written to select tenants on `creds['meta']['ig_user_id']` while the Meta form only ever exposed `account_id`. Nothing tied the two ends together, so the gap was invisible to every test.
- signature: `python3 -m pytest tests/test_identity_fields_collectable.py -q`
- long_term_fix: pin consumers and form together — every platform in `artist_readiness._PLATFORMS` maps to a `(tab, field)` present in `_registry.PLATFORMS`. A new platform must be added to the map, so the omission fails loudly rather than shipping unconnectable.
- autofix: none
- guard: { type: test, ref: tests/test_identity_fields_collectable.py }
- rex_ref: src/dashboard/views/credentials/_registry.py
- first_seen: 2026-08-20 (Instagram unconnectable since the central-app migration)
- History:
  - 2026-08-20: discovered while wiring the onboarding recommendation "Spotify + Instagram" — Instagram could not be connected at all. `instagram_api_collector` told the artist to "verify ig_user_id in Dashboard → Credentials → Meta"; that field did not exist. Field added + connection test extended to probe the IG account; guard pins the mapping.

## guide-single-os-shortcut
- status: guarded
- severity: P3
- kind: deterministic
- symptom: setup-guide prose spells a keyboard shortcut for one OS family (`Ctrl+U`, `Ctrl+F`, `F12`). A macOS artist following the guide literally is blocked at that step — those keys do nothing there — and the guide gives no alternative.
- root_cause: guides were written on the machine the author had. Nothing in the content model could express "this differs per platform", so the first spelling written became the only one.
- signature: `! grep -rnE --include=*.py "Ctrl\+[A-Z]|F12" src/dashboard/content/ src/dashboard/views/credentials/ src/dashboard/utils/i18n_catalog/credentials.py`
- long_term_fix: guide prose carries `{{TOKEN}}` placeholders (`src/dashboard/utils/os_hints.py`) resolved at render time — per-session OS for the dashboard (auto-detected from User-Agent, switchable), both spellings for the emailed PDF, which cannot know the reader's machine.
- autofix: none
- guard: { type: test, ref: tests/test_os_hints.py }
- rex_ref: src/dashboard/utils/os_hints.py
- first_seen: 2026-08-12 (beta session Grinch — tester on macOS)
- History:
  - 2026-08-20: signature corrected the same day — without `--include=*.py` it matched stale `__pycache__/*.pyc` compiled from the pre-fix source and reported a permanent false hit in `audit_runner --deterministic` (CI-blocking). A signature that greps a source tree must exclude build artefacts.
  - 2026-08-20: 7 sites tokenised across FR content, EN content, the SoundCloud in-tab guide and the EN catalog. Signature proven non-zero on the pre-fix tree, zero after. Note the class is not limited to keyboard shortcuts — `FILE_MANAGER` / `DOWNLOADS_DIR` tokens exist for the Explorer-vs-Finder variant of the same defect.

## first-paint-chart-overload
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a view opens on several charts that all bear on the same decision. Nothing is wrong with any single chart; together they leave the artist unable to say what to do next, and the view reads as a report rather than a tool.
- root_cause: charts accumulate additively — each is defensible when added, and no surface ever states a budget, so nobody is the one who removes.
- signature: `python3 -m pytest tests/test_chart_budget.py -q`
- long_term_fix: a chart is PRIMARY only if, alone, it can change what the artist does next; everything that refines goes inside `secondary_analyses()` (`src/dashboard/utils/ui.py`), collapsed — relocation, never deletion. `tests/test_chart_budget.py` holds a per-view first-paint budget that ratchets down: lowering is free, raising requires a deliberate edit.
- autofix: none
- guard: { type: test, ref: tests/test_chart_budget.py }
- rex_ref: src/dashboard/utils/ui.py
- first_seen: 2026-08-12 (beta session Grinch — "réduire le nombre de graphs qui permettent de prendre décision")
- History:
  - 2026-08-20: first pass on the artist-facing views — instagram 4→2 on open, soundcloud 2→1, spotify_s4a_combined 4→3. Guard proven red on the pre-pass tree. The decision rule itself is an engineering judgement, not yet sourced: the `ux-frontend` corpus domain was created to confront it with the literature (`/mnt/c/Users/timot/knowledge/books/ux-frontend/`, empty until books are supplied).

## tenant-identity-falls-back-to-admin
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a per-tenant IDENTITY (`user_id`, `channel_id`, `account_id`, `ig_user_id`, `spotify_artist_id`) resolves to an environment variable, a hardcoded default or another tenant's value when the tenant's own is missing. The env vars hold the ADMIN's identity, so the tenant receives the admin's data — written under the tenant's own `artist_id`, where their dashboard renders it as theirs.
- root_cause: the central-app model (ADR-006) legitimately falls back to env for the shared APP credentials (`client_id`, `api_key`, `access_token`). The same `x or os.getenv(...)` shape was then applied to the tenant identity, where it means something entirely different. Amplified by three reads that returned an empty value on failure — `load_platform_credentials` returned `{}` on any DB error, `get_active_artists` returned `[]` on a DB error *and* on an unknown/inactive `artist_id`, and an empty-string identity is falsy — so an outage, a typo, or an artist saving a blank form all landed on the same fallback.
- signature: `python3 -m pytest tests/test_e2e_two_tenants.py -q`
- long_term_fix: identity has no default. Absent (including `""`) ⇒ skip the tenant with a message naming the next action. Store failure ⇒ `CredentialLoadError`; unknown artist ⇒ `UnknownArtistError`; "no active tenant" is the only `[]`. The legacy single-tenant path is opt-in behind `LEGACY_SINGLE_TENANT=1`. The credentials form no longer persists an empty identity. `docker-compose*.yml` no longer carries the admin's ids as defaults.
- autofix: none
- guard: { type: test, ref: tests/test_e2e_two_tenants.py }
- rex_ref: src/utils/credential_loader.py
- first_seen: 2026-06-15 (Benken), recurred 2026-08-12 (Grinch)
- History:
  - 2026-08-20: two beta sessions, same double symptom ("all credentials failed" + "the data was the admin's"). Sites fixed: `soundcloud_daily.py:103`, `youtube_daily.py:79`, `meta_ads_api_collector.py:81`, `soundcloud_api_collector.py:46`, plus `spotify_api_daily.py` (tenant #1's app credentials served the whole fleet; `SPOTIFY_ARTIST_IDS` folded the admin into every run). Guard proven: **7 failed / 2 passed** on the unpatched tree, 9 passed after. Two pre-existing tests asserted the defective contract (`test_db_error_returns_empty`) and were inverted.
  - 2026-08-20: adjacent finding surfaced by the guard itself — nothing constrains `saas_artists.spotify_artist_id` to one tenant, and the DAG took `_sa[0][0]`, attributing a whole catalogue to whichever tenant had the lower id. Ambiguous ownership now skips with both ids logged.

## write-without-explicit-artist-id
- status: guarded
- severity: P1
- kind: deterministic
- symptom: an upsert payload omits the `artist_id` key on a tenant-scoped table. `upsert_many` derives the INSERT column list from the payload keys (`postgres_handler.py:332`), so the column is absent from the statement and Postgres applies `DEFAULT 1` — every tenant's rows silently accumulate under the admin. No error, no warning, no alert.
- root_cause: ~80 tables declare `artist_id INTEGER DEFAULT 1`, a single-tenant leftover. The default turns "the developer forgot the tenant" into "the admin owns it" instead of into a constraint violation.
- signature: `python3 .claude/scripts/audit_tenant_writes.py`
- long_term_fix: every write names its tenant. The guard walks the payload of each `upsert_many` call made during a real collection run and fails when a tenant-scoped table receives a payload without an `artist_id` key. Removing the `DEFAULT 1` from the schema is the durable follow-up (a dedicated migration, after the write paths are correct).
- autofix: none
- guard: { type: test, ref: tests/test_e2e_two_tenants.py }
- rex_ref: airflow/dags/spotify_api_daily.py
- first_seen: 2026-08-20
- History:
  - 2026-08-20: signature promoted from the DB-gated E2E to a repo-wide AST+SQL scan (`audit_tenant_writes.py`): it learns the tenant-scoped tables from `init_db.sql`+migrations (80 of them), resolves each `upsert_many` payload and every raw `INSERT INTO`, and reports what it cannot resolve rather than passing it. Proven **1 MISSING before the fix, 0 after**.
  - 2026-08-20: found while auditing the two failed beta sessions. `track_popularity_history` had been storing EVERY tenant's Spotify popularity history under `artist_id = 1` since the multi-tenant migration — daily, in production, undetected, because nothing ever compared the payload to the schema. A row whose tenant cannot be resolved is now skipped with a warning rather than attributed to the admin. Latent sibling fixed at the same time: `youtube_comments` (dormant, `collect_comments=False`).

## upsert-transfers-row-ownership
- status: guarded
- severity: P1
- kind: deterministic
- symptom: an upsert whose `conflict_columns` is a global PLATFORM id carries `artist_id` in its `update_columns`. Two tenants touching the same object do not get a row each — the second collection re-assigns the existing row, and the first tenant's data vanishes from their (artist-scoped) views. `youtube_videos` even declared `UNIQUE(video_id)`, making single ownership structural.
- root_cause: the tables were designed single-tenant, where the platform id *is* the natural key. `artist_id` was later added to `update_columns` so it could be backfilled — which turned every conflict into a transfer of ownership.
- signature: `python3 -m pytest tests/test_e2e_two_tenants.py -q -k ownership`
- long_term_fix: migration 064 makes uniqueness `(artist_id, video_id)` / `(artist_id, channel_id)`; `artist_id` is removed from every `update_columns`, so a row keeps its first owner. `meta_campaigns/adsets/ads` keep their platform-id primary keys (15 FKs reference them) but lose the reassignment — a shared ad account can no longer steal a row.
- autofix: none
- guard: { type: test, ref: tests/test_e2e_two_tenants.py }
- rex_ref: migrations/064_tenant_scoped_uniqueness.sql
- first_seen: 2026-08-20
- History:
  - 2026-08-20: reproduced live on a provisioned Postgres — two tenants collecting the same channel, the first tenant's `youtube_videos` row disappeared. The theft is what made the identity fallback *persist*: even after fixing the identity, rows already written stayed re-attributed. `tools/tenant_contamination_check.py` measures the remaining damage.

## dag-trigger-without-tenant-scope
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a dashboard action triggers a DAG without `conf={'artist_id': …}`. The API collectors then run fleet-wide, and the CSV watchers — which defaulted to `artist_id = 1` — parse the SHARED drop directory into the admin's tenant. Reachable by any logged-in artist.
- root_cause: the sidebar "🚀 Lancer TOUTES les collectes" button predates multi-tenancy and was never revisited; it was also rendered before any role gate. The verification e-mail sent at sign-up tells every new artist to press it.
- signature: `! grep -rn --include=*.py "trigger_dag(" src/dashboard/ | grep -v "conf="`
- long_term_fix: every trigger carries the tenant; a non-admin without a resolved `artist_id` triggers nothing; the CSV watchers have no default tenant — a manual trigger without `artist_id` raises, and a *scheduled* run (which legitimately has no conf) reports the unattributable files and writes nothing.
- autofix: none
- guard: { type: error-class-signature, ref: audit_runner --deterministic }
- rex_ref: src/dashboard/app.py
- first_seen: 2026-08-20
- History:
  - 2026-08-20: 1 hit (`app.py:348`), 0 after the fix. Found while tracing how an artist could write into tenant 1 without admin rights.

## ast-guard-blind-to-bom
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a source file starts with a UTF-8 BOM (`\xef\xbb\xbf`). `ast.parse` on text read with plain `encoding="utf-8"` raises `SyntaxError: invalid non-printable character U+FEFF`, so every AST-based guard **silently scans nothing** in that file. The file looks covered; it is not.
- root_cause: files edited on Windows acquire a BOM; Python tolerates it at runtime (the interpreter strips it) but `ast.parse` on an already-decoded string does not. A guard that catches `SyntaxError` and moves on turns the blind spot into a pass.
- signature: `python3 -c "import sys;from pathlib import Path;bad=[str(p) for d in ('src','airflow','tests','.claude/scripts') for p in Path(d).rglob('*.py') if p.read_bytes()[:3]==b'\xef\xbb\xbf'];print(chr(10).join(bad));sys.exit(1 if bad else 0)"`
- long_term_fix: no BOM in the repo (3 removed), AST tools read with `encoding="utf-8-sig"`, and an unparsable file is REPORTED as a failure rather than skipped — a file the scanner could not read is not a file that passed.
- autofix: safe
- guard: { type: error-class-signature, ref: audit_runner --deterministic }
- rex_ref: .claude/scripts/audit_tenant_writes.py
- first_seen: 2026-08-20
- History:
  - 2026-08-20: signature polarity corrected the same day — the `! cmd` idiom fits grep (exit 0 on a hit); this probe already exits 1 when a BOM exists, so the `!` inverted it and reported a permanent false hit. An idiom copied without checking its polarity is a guard that reads backwards.
  - 2026-08-20: discovered while checking that a NEW guard actually went red on the defect it targets — it did not, because `spotify_api_daily.py` carried a BOM and was being skipped. The same BOM explains the "3 fichiers non parsables — graphe incomplet" that `select_tests.py` (CLAUDE.md rule 16) had been printing on every run: the impact graph was silently missing three DAGs. `tests/test_dag_fleet_isolation.py` was unaffected (it already read `utf-8-sig`).

## migration-ahead-of-its-code
- status: reported
- severity: P1
- kind: manual
- symptom: a migration that changes a **key** (primary key, unique constraint, conflict target) is applied to production while the code that uses the new key is not yet deployed. Every `ON CONFLICT` upsert against the old target then fails with `there is no unique or exclusion constraint matching the ON CONFLICT specification`, and collection stops.
- root_cause: migrations are treated as independently deployable because most of them are — adding a column, an index, a table is forward-compatible in both directions. A key change is not: it is a contract between the schema and the writer, and applying half a contract breaks the half that is live.
- signature: manual — a migration touching PRIMARY KEY / UNIQUE / a conflict target must carry an explicit deployment-order note and be applied AFTER the deploy.
- long_term_fix: two classes of migration, stated at the top of the file. **Additive** (column, index, table, default) → may precede the code. **Key-changing** (PK, UNIQUE, conflict target) → the file must open with an ORDER OF DEPLOYMENT banner and be applied only after `make deploy`. `migrations/065_youtube_surrogate_pk.sql` carries the first such banner.
- autofix: none
- guard: { type: doc-convention, ref: migrations/065_youtube_surrogate_pk.sql }
- rex_ref: migrations/065_youtube_surrogate_pk.sql
- first_seen: 2026-08-20
- History:
  - 2026-08-20: caused by me, in production, while fixing the tenant-isolation bugs. Migration 064 (additive indexes) was safe; 065 moved the primary key of `youtube_channels`/`youtube_videos` off the platform id, and the deployed collector still upserted on `ON CONFLICT (channel_id)`. Detected within minutes because the collection run that was meant to PROVE the fix reported `failed` for every tenant with a channel; reverted on the spot and collection was restored (the admin's 67 videos came back under the admin). The lesson is not "test more" — the migration was tested against a clone of the production schema and passed. It is that a key change is only correct in the presence of its writer.

## column-name-is-not-its-meaning
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a sweep, a migration or a guard treats every column sharing a NAME as sharing a MEANING. In this schema `artist_id` is the tenant (INTEGER) on ~55 tables and the **Spotify artist id** (VARCHAR) on three legacy ones — `artists`, `artist_history`, `tracks`, where the tenant is `saas_artist_id`.
- root_cause: the multi-tenant migration reused the `artist_id` name for the new tenant column while the old single-tenant tables kept it for the platform id. Two meanings, one name, and nothing in the schema says which is which except the type.
- signature: `python3 .claude/scripts/audit_tenant_writes.py`
- long_term_fix: reason on the TYPE, never on the name — a tenant column is `INTEGER`. The write auditor and migration 068 both filter on `data_type = 'integer'`, and 068 carries the note so the next migration does not relearn it.
- autofix: none
- guard: { type: test, ref: tests/test_e2e_two_tenants.py }
- rex_ref: migrations/068_drop_artist_id_defaults.sql
- first_seen: 2026-08-20
- History:
  - 2026-08-20: a first version of migration 068 set `NOT NULL` on every column named `artist_id`, including `tracks.artist_id` — the Spotify id, which the collector legitimately writes and which the test fixture did not provide. The full suite went red against a database carrying the migration, which is exactly what running it against a provisioned schema is for. Filtering on the type fixed it, and `tracks.saas_artist_id` is excluded from NOT NULL on purpose: a track no tenant claims belongs in the catalogue with a NULL owner rather than an invented one.

## identity-claimed-by-two-tenants
- status: guarded
- severity: P2
- kind: deterministic
- symptom: two artists declare the same platform identity (SoundCloud user_id, YouTube channel, Meta ad account, Spotify artist). Nothing refuses it. Both accounts then collect the same upstream data, and any consumer that resolves a tenant FROM the identity has to guess.
- root_cause: the identity is stored per-artist in `artist_credentials.extra_config` (JSONB) with no cross-tenant constraint, and the form validated the value's shape but never its exclusivity.
- signature: `python3 -m pytest tests/test_identity_uniqueness.py -q`
- long_term_fix: `find_identity_conflict()` (`credentials/_core.py`) is called at SAVE time — the only moment a human is present to fix it — and refuses with the field and value named. `spotify_api_daily` additionally refuses to collect an ambiguous id instead of taking the lowest artist_id. A test pins that every platform in the credentials registry has a uniqueness rule, so a new platform cannot be added without one.
- autofix: none
- guard: { type: test, ref: tests/test_identity_uniqueness.py }
- rex_ref: src/dashboard/views/credentials/_core.py
- first_seen: 2026-08-20
- History:
  - 2026-08-20: surfaced by a guard, not by a report — a canary tenant created during the session reused the admin's `spotify_artist_id`, and the E2E test attributed the catalogue to the wrong account. `_sa[0][0]` had been silently picking the lower id.

## probe-scoped-to-the-machine-not-the-repo
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a health probe enumerates every container or process on the HOST instead of the ones this repo declares. It reports on neighbouring projects — and can read **green** because a neighbour is running while this repo is down.
- root_cause: `.claude/hooks/session_summary.py` carried `_MSDR_CONTAINERS = ("msdr_api", "msdr_dashboard", "msdr_receiver")`, a literal list from the repo the baseline payload was cut from; `.claude/scripts/check_env.py::check_docker_tz_utc` iterated `docker ps` with no filter at all.
- signature: `python3 -m pytest tests/test_probes_scoped_to_repo.py -q`
- long_term_fix: both probes derive their expected set from the `container_name:` entries **this repo's own compose file** declares (`_expected_containers` / `_declared_container_names`). A payload copied to another repo then adapts instead of lying, and an empty set degrades to silence rather than to a false positive.
- autofix: none
- guard: { type: test, ref: tests/test_probes_scoped_to_repo.py }
- rex_ref: .claude/commands/check-env.md
- first_seen: 2026-08-21 (ref: roadmap R36)
- History:
  - 2026-08-21: found by the R36 domain-leak sweep, not by a report — which is the point. The Stop hook had reported Docker health for weeks; `msdr_api`, `msdr_dashboard` and `msdr_receiver` were all running on this machine, so it printed nothing while this repo's `postgres_spotify_airflow` was down. The TZ probe was louder and therefore easier to catch: it told the user to edit the environment block of `n8n-ollama` and `n8n-postgres`. Guard verified red (4 failures) against the pre-fix modules, green after.

## state-path-namespaced-by-another-project
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a writer and its readers disagree on where shared state lives, because one of them hardcodes a project name in the path. Nothing errors — the reader simply reads a file that stopped growing, and the feature built on it goes quietly inert.
- root_cause: `.claude/hooks/observe.py` wrote to `.claude/homunculus/msdr/observations.jsonl` while `.claude/hooks/draft_devlog.py` read `.claude/homunculus/<repo name>/observations.jsonl`. Both are correct in isolation; only together are they a bug.
- signature: `python3 -m pytest tests/test_probes_scoped_to_repo.py -q`
- long_term_fix: every homunculus path is derived from `repo_root.name`, never written as a literal (`observe.py`, `draft_rex.py`, `session_summary.py` aligned on the form `sensor.py` and `draft_devlog.py` already used). A test rejects a literal directory segment under `.claude/homunculus/`, so writer and readers cannot diverge again.
- autofix: none
- guard: { type: test, ref: tests/test_probes_scoped_to_repo.py }
- rex_ref: .claude/skills/verification/SKILL.md
- first_seen: 2026-08-21 (ref: roadmap R36)
- History:
  - 2026-08-21: dated by the data itself. `homunculus/<project>/observations.jsonl` holds 536 entries and stops on 2026-07-28 — the day the payload was re-pushed with an `observe.py` that hardcoded `msdr`; `homunculus/msdr/observations.jsonl` holds the 74 entries written since. `draft_devlog.py` had been drafting from the frozen file for three weeks, which is why `.claude/sessions/pending-devlog.md` sat at 2026-05-15 with every field still `?`. The 74 orphaned entries were merged back (606 unique, chronological) and the stray directory retired. A third namespace, `homunculus/streamlytics/`, was found empty and referenced by no code — removed.
