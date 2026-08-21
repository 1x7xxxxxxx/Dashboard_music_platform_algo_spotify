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
| [migrate-heals-only-if-run-to-completion](#migrate-heals-only-if-run-to-completion) | P2 | deterministic | guarded | none |
| [freshness-measured-on-write-time](#freshness-measured-on-write-time) | P2 | deterministic | guarded | none |
| [dag-conf-honoured-by-one-task-only](#dag-conf-honoured-by-one-task-only) | P3 | deterministic | guarded | none |
| [local-db-drifts-from-canonical](#local-db-drifts-from-canonical) | P3 | manual | reported | none |

| [ci-runs-twice-for-one-commit](#ci-runs-twice-for-one-commit) | — | deterministic | guarded | — |
| [ci-has-no-concurrency-group](#ci-has-no-concurrency-group) | — | deterministic | guarded | — |
| [env-resolved-against-cwd](#env-resolved-against-cwd) | P2 | deterministic | fixed | none |
| [identity-mirrored-but-written-once](#identity-mirrored-but-written-once) | P1 | deterministic | fixed | none |
| [api-partial-date-into-date-column](#api-partial-date-into-date-column) | P2 | deterministic | fixed | none |
| [unguarded-drop-replayed-alone](#unguarded-drop-replayed-alone) | P1 | deterministic | fixed | none |
| [suite-runs-against-one-tenant](#suite-runs-against-one-tenant) | P1 | deterministic | fixed | none |
| [script-unreachable-from-its-dependencies](#script-unreachable-from-its-dependencies) | P2 | deterministic | fixed | none |
| [finding-rendered-but-not-alerted](#finding-rendered-but-not-alerted) | P1 | deterministic | fixed | none |
| [canary-tenant-unwatched](#canary-tenant-unwatched) | P2 | deterministic | fixed | none |
| [watchdog-becomes-the-noise](#watchdog-becomes-the-noise) | P3 | deterministic | fixed | none |
| [app-id-confused-with-ad-account-id](#app-id-confused-with-ad-account-id) | P2 | heuristic | fixed | none |
| [suppressed-alert-renders-as-health](#suppressed-alert-renders-as-health) | P2 | deterministic | guarded | none |
| [catalogue-index-omits-its-own-entries](#catalogue-index-omits-its-own-entries) | P3 | deterministic | guarded | none |
| [same-platform-judged-on-different-tables](#same-platform-judged-on-different-tables) | P2 | deterministic | guarded | none |
| [map-key-unreachable-by-construction](#map-key-unreachable-by-construction) | P2 | deterministic | guarded | none |
| [guard-derived-from-the-thing-it-guards](#guard-derived-from-the-thing-it-guards) | P2 | deterministic | guarded | none |
| [broken-probe-rendered-as-user-fault](#broken-probe-rendered-as-user-fault) | P2 | deterministic | guarded | none |
| [row-existence-read-as-connection](#row-existence-read-as-connection) | P2 | deterministic | guarded | none |
| [config-corrected-in-the-file-that-loses](#config-corrected-in-the-file-that-loses) | P2 | manual | guarded | none |

> A `—` cell means the entry itself declares no such field. The two CI-waste classes
> arrived from another repo in a looser format; no severity has been invented for them.

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
  - 2026-08-22: third shape — not a test that proves the wrong thing, a platform with **no test at all**. Instagram was probed only as an optional suffix inside `_test_meta`, skipped when the id was blank, so `tools/artist_preflight.py` step 3 (which iterates `CONNECTION_TESTS`) never covered it and no artist ever got a verdict on it. `_test_instagram` is now a first-class entry and returns False — never True — on a blank identity. Coverage is asserted against the LOGICAL platforms, not the four form tabs: judging it by tabs is what hid the gap, since Instagram is a field of the Meta tab.
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
  - 2026-08-22: last surviving site closed — `src/collectors/instagram_api_collector.py:43` still read `ig_user_id or os.getenv("INSTAGRAM_USER_ID")`. Unreachable through the DAG (which skips blanks) and reachable by any direct instantiation. The existing pytest signature could not have caught it because the DAG path was already correct; the new guard is an **AST sweep** over collectors and DAGs for `<x> or os.getenv(<identity var>)`. AST is mandatory here: the removed variable names appear in the explanatory comments of the very files checked, so a grep would be permanently red on the documentation of its own fix.
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
  - 2026-08-22: the rule existed and Instagram was **exempt from it** — `UNIQUE_IDENTITY_FIELDS` had four entries against a five-entry registry, so `find_identity_conflict` returned None and two tenants could claim the same Instagram Business Account in silence. The map now derives from `tenant_identity.PLATFORM_IDENTITIES`, and the lookup queries the STORAGE platform (`meta`) because a `platform='instagram'` row does not exist. See `guard-derived-from-the-thing-it-guards` for why no test failed.
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
  - 2026-08-21 (same day, second shape): the class is not only about SCOPE but about ASSERTED VALUE. Two more probes in `check_env.py` demanded what another deployment needed — `TZ=UTC` on containers that declare `Europe/Paris` on purpose (Airflow already runs `core.default_timezone = utc`), and a UTC host clock, which no developer machine has. Both were the false positives in a 7/10 score. Rewritten to measure what can actually go wrong: containers must AGREE on a zone, and the host clock must be NTP-synchronised — drift breaks Stripe's five-minute webhook tolerance and JWT expiry, while the zone is a display preference. Score now 9/10 with one true warning. Guard extended, verified red on the old probes.

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

## migrate-heals-only-if-run-to-completion
- status: guarded
- severity: P2
- kind: deterministic
- symptom: `make migrate` prints success while `psql` errors scroll past. The full run is self-consistent, so nothing looks wrong — but a run interrupted at the wrong file leaves production without a constraint, and nobody is told.
- root_cause: `psql` without `ON_ERROR_STOP` exits 0 even when statements failed, and the `migrate` recipe discarded that output. The individual files are not idempotent: `migrations/024` drops `s4a_song_playlist_adds_pkey` unconditionally and fails to recreate it (the key became window-aware in `044`, which restores it). 001..N is correct; 001..024 is a table with no primary key.
- signature: `python3 -m pytest tests/test_migrate_reports_errors.py -q`
- long_term_fix: the migrate logic lives in `tools/migrate.sh` (so it runs where `make` is absent — R37), keeps going after an error (that is what lets 044 heal 024), and **classifies** what it saw: re-run artefacts counted, unexpected errors named with their message plus the command that proves the schema landed (`make schema-check`). Silence and noise are both impossible outcomes. `tests/test_migrate_reports_errors.py` pins capture, inspection, naming, the classification, and that migrations stay runnable without `make`.
- autofix: none
- guard: { type: test, ref: tests/test_migrate_reports_errors.py }
- rex_ref: .claude/rules/makefile-fail-fast.md
- first_seen: 2026-08-21 (ref: roadmap R25/R26 production deploy)
- History:
  - 2026-08-21: found during the real production migration run, not in a test. Applying every `migrations/*.sql` on the live database surfaced one error — `could not create unique index "s4a_song_playlist_adds_pkey"` — which the target would have swallowed. Verified afterwards that the constraint was intact in its later 4-column form, because `044` runs after `024` in the same pass. Sibling of `migration-ahead-of-its-code`: both are about migration ORDER being load-bearing while nothing enforces it.
  - 2026-08-21 (same day): the guard nearly became the defect it names. Its first real production run reported FIVE files — 002, 011, 019, 023, 024 — of which four were `already exists` / `does not exist`, the normal outcome of re-applying a migration written before `IF NOT EXISTS`. A report whose four fifths are noise teaches the reader to skip all of it, and the one line that matters disappears with the rest. Fixed by CLASSIFYING rather than filtering: re-run artefacts are counted on one line, unexpected errors are named with their message. Filtering would have been the obvious move and the wrong one — a genuine `relation … does not exist` must stay visible, it may just no longer hide in the noise. Verified on production: `ℹ️ 4 re-applied over existing objects / ⚠️ 1 not a re-run artefact`, and the schema still canonical at 917 cols / 91 tables.

## freshness-measured-on-write-time
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a source is reported FRESH while its data is months or years old. The collector still runs and still writes, so the write timestamp advances nightly — it simply writes the same old rows.
- root_cause: `freshness_monitor.MONITOR_TARGETS` measured `MAX(collected_at)` for all seven sources, including the three tables that record the day their data is ABOUT separately from the day it landed (`meta_insights_performance_day.day_date`, `s4a_song_timeline.date`, `track_popularity_history.date`). "Written recently" was being read as "describes a recent day"; they are different claims.
- signature: `python3 -m pytest tests/test_freshness_measures_the_right_column.py -q`
- long_term_fix: a target may declare `metric_col` (and `tenant_metric_col`), and freshness prefers it over the write column. Each result carries `measured_on` — `metric` or `write` — so a reader knows which of the two claims is being made. The guard checks BOTH directions against the live schema: a monitored table that has a metric-date column must declare it, and a snapshot table must not declare one it lacks (that would render as a permanent red light on a healthy source — the other way to make a monitor unreadable).
- autofix: none
- guard: { type: test, ref: tests/test_freshness_measures_the_right_column.py }
- rex_ref: src/utils/freshness_monitor.py
- first_seen: 2026-08-21 (ref: roadmap R13)
- History:
  - 2026-08-21: found while checking whether the newly-scheduled central-app task would actually detect R13. It would not — and neither would freshness. Measured on production: `meta_insights_performance_day` had `MAX(collected_at)` = that morning 07:01, `MAX(day_date)` = **2024-09-30**, and **zero** rows with a `day_date` inside the last seven days. Meta Ads had collected nothing since early August behind a green light. After the fix the same probe reports **16 577 hours** stale (~23 months), and surfaces two more genuinely stale CSV sources (Spotify S4A 1 817 h, Apple Music 1 605 h). Guard verified 3 red before / 6 green after. Sibling of `connection-test-proves-app-not-tenant` and of the `psql` exit-0 case: each time the measurement and the question were about different things.

## dag-conf-honoured-by-one-task-only
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a per-tenant trigger from the dashboard (`conf={'artist_id': …}`) scopes the first task of a DAG and runs the next one over the whole fleet. Nothing fails, nothing is misfiled — the work is simply done for everyone, on every click.
- root_cause: `spotify_api_daily.collect_spotify_artists` reads `dag_run.conf['artist_id']`; `collect_spotify_top_tracks`, in the same DAG, never looked at the context and selected its work with `SELECT artist_id FROM artists` — the entire Spotify catalogue.
- signature: `python3 -m pytest tests/test_e2e_two_tenants.py::test_spotify_popularity_history_carries_its_tenant -q`
- long_term_fix: the task reads the conf and, when present, resolves the tenant's own `spotify_artist_id`; an active tenant with no Spotify id logs which tenant and returns 0 instead of falling through to the fleet query. The guard drives the DAG the way the dashboard does — scoped — so a task that ignores the scope produces a payload for more than one tenant and fails.
- autofix: none
- guard: { type: test, ref: tests/test_e2e_two_tenants.py }
- rex_ref: airflow/dags/spotify_api_daily.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: found by running the suite against the real local database for the first time (R18 unblocked `make up`). The test had always passed because a throwaway database holds exactly one tenant — with a second, the scoped call built a payload for `{1, 223}`. The first reading was "the DAG leaks"; it does not, every row carries its own tenant. What it does is fetch every tenant's top tracks from the Spotify API on a per-tenant click — wasted quota against a rate-limited API this repo already has a whole failure strategy for. The test itself was the second defect: `assert artist_ids == {tenant}` only held on an empty fleet, so it would have cried wolf the day CI got data.

## local-db-drifts-from-canonical
- status: reported
- severity: P3
- kind: manual
- symptom: tests pass in CI and against a throwaway database, and fail on the developer's own machine — with type errors, not logic errors.
- root_cause: `make schema-check` compares PRODUCTION against canonical (`init_db.sql` + `migrations/*.sql`). Nothing compares the LOCAL development database, which predates several migrations and drifted silently. Measured 2026-08-21: `soundcloud_tracks_daily.track_id` was `bigint` locally against `VARCHAR(50)` canonical, breaking 7 tests with `invalid input syntax for type bigint`.
- signature: `make schema-check PROD_SSH=<user@host>` — compares prod only; the local comparison is the gap this class names
- long_term_fix: — (reported, not guarded). The full diff was: 0 missing columns, 0 extra columns, 26 type differences of which 24 are `text` vs `character varying` (equivalent in Postgres — a `VARCHAR` with no length IS `text`) and 2 are widenings that do not bite. Only `track_id` had behaviour. A `make schema-check LOCAL=1` would close it; the measurement above is what would justify writing it.
- autofix: none
- guard: { type: cross-cutting-rule, ref: .claude/dev-docs/runbook-actions-utilisateur.md }
- rex_ref: .claude/scripts/check_env.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: surfaced the first time the suite ran against the local database instead of a throwaway one. The local column was converted (349 rows preserved). Worth knowing before writing the guard: most of the "drift" is cosmetic, so a naive column-type comparison would report 26 findings of which 24 are noise — the same cry-wolf failure the migrate reporter hit the same day.

## env-resolved-against-cwd
- status: fixed
- severity: P2
- kind: deterministic
- symptom: a tool reports "credential NOT configured" for a credential that is configured, or a process silently runs with no configuration at all. The red names the wrong cause, so the fix is attempted on the wrong thing.
- root_cause: the `.env` file is resolved against the **caller's current working directory** rather than the repository root. `load_dotenv('.env')` returns `False` when the file is not there and raises nothing — the absence is indistinguishable from success. Measured 2026-08-21 on two sites: `make artist-preflight` printed "❌ Spotify central app NOT configured" from a shell where the credentials were merely unloaded, and `src/dashboard/app.py` tested `os.path.exists('.env.local')` from a cwd of `src/dashboard/` — which is exactly the launch documented in CLAUDE.md — loading nothing.
- signature: `! grep -rlE "(exists|load_dotenv)\(['\"]\.env" src/ tools/ --include=*.py | grep -v env_files.py`
- long_term_fix: `src/utils/env_files.py` resolves `.env.local` then `.env` against `Path(__file__).parent.parent.parent`, so the result does not depend on the caller's cwd. Every shell entrypoint calls `load_project_env()`. An already-injected variable always wins, so a stale file inside a container cannot override the real environment.
- autofix: none
- guard: { type: pytest, ref: tests/test_env_is_root_anchored.py }
- secondary_signature: `python3 -m pytest tests/test_operator_tools_read_the_apps_env.py -q`
- rex_ref: tools/artist_preflight.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: mutation-verified — reinstating the cwd-relative form in `src/dashboard/app.py` turns 2 of the 12 assertions red, and restoring the loader turns them green.
  - 2026-08-22: **a sibling the signature could not see.** `tools/check_central_apps.py` — the command the runbook and the roadmap tell an operator to run to prove the shared apps authenticate — never called `load_project_env()` at all. From a bare shell it printed `⚠️ env not set` for all four platforms and exited **0**. The signature greps for the *wrong form* (`load_dotenv('.env')`); this defect was the *missing form*, and an absence matches no pattern. Added `tests/test_operator_tools_read_the_apps_env.py`, which derives its subjects from the tools the documentation tells an operator to run, so a newly-documented tool is covered the day it is documented. Same day, same class: `tools/notify_schema_drift.py` restated the file order as `.env` only — it cannot import the app package by design, so its order is copied, and a copied order drifts. The test now pins it against `env_files.ENV_FILES`.

## identity-mirrored-but-written-once
- status: fixed
- severity: P1
- kind: deterministic
- symptom: a tenant shows as connected on every screen, passes its connection test, and collects nothing. The DAG succeeds in under a second.
- root_cause: one tenant identity is stored in TWO places — `artist_credentials.extra_config` (read by every screen and every readiness check) and `saas_artists.spotify_artist_id` (read by `spotify_api_daily` to decide whose catalogue to collect). The credentials form wrote both; `tools/create_canary.py` wrote only the first. Measured 2026-08-21: canary tenant 471 reported "Connecté — artiste « Daft Punk » ✅" everywhere while its DAG logged "aucun spotify_artist_id déclaré" and wrote 0 rows. The tenant whose entire purpose is to catch a false green WAS the false green.
- signature: `! grep -rn "UPDATE saas_artists SET spotify_artist_id" src/ tools/ --include=*.py | grep -v tenant_identity.py`
- long_term_fix: `src/utils/tenant_identity.py` holds `IDENTITY_MIRRORS` and `write_platform_identity()` — the single path that writes the credentials row AND every mirror the platform declares. Both writers call it; no third writer can get it half right.
- autofix: none
- guard: { type: pytest, ref: tests/test_tenant_identity_mirrors.py }
- rex_ref: tools/create_canary.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: verifying a signature BY HAND in an interactive shell is unreliable here — `grep` is a shell function (the RTK wrapper), and it returns 0 whenever stdout is redirected, whatever it matched. Both signatures above looked constant-and-hollow under `! grep … > /dev/null` and were in fact correct. Verify a signature through `audit_runner.py`, which runs the real binary, or prefix `command grep`. The instrument was the defect, not the signature.
  - 2026-08-21: the guard's FIRST version was vacuous — it asserted `"write_platform_identity" in text`, which the import line satisfied on its own, so deleting the call left it green. Rewritten on the AST to require an actual `ast.Call`. Only then did the mutation turn it red. A guard that tests for a substring tests the import, not the behaviour.

## api-partial-date-into-date-column
- status: fixed
- severity: P2
- kind: deterministic
- symptom: a collector fails with `invalid input syntax for type date: "2013"` and the artist loses EVERY row of that run, not just the offending one. Latent for years, then fires the first time a second tenant is collected.
- root_cause: Spotify returns `album.release_date` at a precision it declares separately in `album.release_date_precision` — `"2013"`, `"2013-05"` or `"2013-05-21"`. `tracks.release_date` is `DATE`, and the value was passed through raw. Because `upsert_many` writes one batch per artist, a single year-precision album aborts the artist's whole batch, after which the DAG raises "collected 0 tracks". A comment sat directly above the line reading *"Gestion sécurisée de la date de sortie (parfois YYYY seulement)"* — describing a handling that did not exist. Measured 2026-08-21.
- signature: `! grep -n "release_date = track\['album'\]\['release_date'\]" src/collectors/spotify_api.py`
- long_term_fix: `src/utils/api_dates.py::coerce_api_date()` accepts all three precisions and pads to the FIRST day of the declared period (never to today, which would read as "released this month" in recency features). An unusable value returns `None` — one column lost instead of the artist's batch. The CSV path already behaved this way implicitly via `pandas.to_datetime`; the two paths now agree.
- autofix: none
- guard: { type: pytest, ref: tests/test_api_partial_dates.py }
- rex_ref: src/collectors/spotify_api.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: found by the canary tenant on its FIRST real collection, minutes after it was created. It had never fired in production because the admin's own catalogue carries full dates only — the defect was invisible to a one-tenant test by construction. This is the concrete payoff of the "run the suite against at least two tenants" lesson, and the single best argument for keeping the canary.
  - 2026-08-21: the comment above the defect claimed the case was handled. A comment is not a guard, and a comment that describes an intention the code does not implement is worse than none — it stops the next reader from looking.

## unguarded-drop-replayed-alone
- status: fixed
- severity: P1
- kind: deterministic
- symptom: a table silently loses its primary key. Nothing errors visibly at the application level; duplicate rows become possible and `ON CONFLICT` upserts start failing or silently inserting.
- root_cause: a migration whose first statement is an unguarded `DROP CONSTRAINT`, replayed on its own. Measured 2026-08-21 while introducing the `schema_migrations` ledger: `024` drops `s4a_song_playlist_adds_pkey` then fails to create its three-column replacement (impossible since `044` made the key window-aware, so the same song legitimately holds several rows per `recorded_at`). That failure was survivable ONLY while the whole set was replayed in order, because `044` ran afterwards and restored the right key. The ledger changed the premise: a file that never succeeds is never recorded, so it is retried ALONE on every run — and each retry destroyed `044`'s key. **The ledger's own introduction is what left the table keyless.** A safety mechanism whose first act is to break the thing it protects.
- signature: `python3 -m pytest tests/test_migrations_are_replay_safe.py -q`
- signature_note: a line-oriented grep CANNOT judge this class — whether a `DROP` is safe depends on an enclosing `DO $$ … END $$` that sits on other lines. The first version accused `061`, which has the correct shape, and `024`'s own explanatory comment. The parser in the test is the only honest detector, so the signature delegates to it instead of approximating it.
- long_term_fix: `024` now opens with a `DO $$` block that returns immediately when `044`'s marker column (`time_window`) is present — it can no longer touch a schema it does not own. `019`'s two unguarded drops were hardened in the same sweep. `tests/test_migrations_are_replay_safe.py` parses every migration and rejects a `DROP` that carries neither `IF EXISTS` nor an enclosing guarded `DO` block, so the class cannot re-enter through a new file.
- autofix: none
- guard: { type: pytest, ref: tests/test_migrations_are_replay_safe.py }
- rex_ref: tools/migrate.sh
- first_seen: 2026-08-21
- History:
  - 2026-08-21: the lesson is about the CHANGE, not the file. Adding a ledger looked purely additive — it only skips work. What it actually did was alter the replay CONTEXT that an unguarded statement had silently depended on for months. Before changing how a set of scripts is executed, ask what each one assumed about its neighbours. `061` had the correct shape all along (test for the constraint, drop, re-add unconditionally, all inside one `DO`) and was unaffected.
  - 2026-08-21: it was found only because the primary key was checked directly in `pg_constraint` after the run, rather than trusting `migrate.sh`'s "✅ no unexpected psql error". The runner was telling the truth about psql and still missing the damage — the effect was one level below what it measured.

## suite-runs-against-one-tenant
- status: fixed
- severity: P1
- kind: deterministic
- symptom: the whole suite is green, CI is green, and multi-tenant defects ship anyway. They surface later, in front of a real artist, as "connected but no data".
- root_cause: a fresh canonical database (`init_db.sql` + every migration) contains exactly ONE tenant — `Artist Default` — and that is what CI has always tested against. With one tenant, "collect for this tenant" and "collect for the whole fleet" return the same rows, so every isolation defect reads as correct behaviour. Measured 2026-08-21: three real defects were found within an hour of a second tenant existing (`identity-mirrored-but-written-once`, `api-partial-date-into-date-column`, `dag-conf-honoured-by-one-task-only`), and NONE of them was reachable before that.
- signature: `python3 -m pytest tests/test_suite_runs_against_two_tenants.py -q`
- long_term_fix: CI seeds a second tenant (`ci-canary`) right after provisioning, with real PUBLIC platform identities deliberately different from tenant 1's — a tenant borrowing another's identity passes every isolation check while proving nothing. Locally the same role is filled by `make canary`. The guard fails when fewer than two active tenants exist and names both fixes.
- autofix: none
- guard: { type: pytest, ref: tests/test_suite_runs_against_two_tenants.py }
- rex_ref: tools/create_canary.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: mutation-verified against a throwaway canonical database — red with the single seeded tenant, green once a second was inserted.
  - 2026-08-21: the cost of NOT having this was two beta sessions burned an hour each on defects every one of these checks would have caught in advance. The fixture is two rows.

## script-unreachable-from-its-dependencies
- status: fixed
- severity: P2
- kind: deterministic
- symptom: a runbook step that reads perfectly cannot be executed anywhere. `can't open file '/app/tools/<script>.py'` from a container, `ModuleNotFoundError: psycopg2` from the host.
- root_cause: the script and its runtime dependency live in different places. `tools/` is on the HOST and is not mounted into any container; `psycopg2` is installed IN the containers and not on the host. Measured 2026-08-21 on the live server while running the documented production procedure for the canary tenant. This is the same split that had already been diagnosed once — `src/utils/central_apps.py` was moved out of `tools/` precisely because `tools/` is not importable inside Airflow — but the lesson was applied to one script and not to its neighbours, which is how a class survives its own fix.
- signature: `python3 -m pytest tests/test_operational_scripts_are_reachable_in_containers.py -q`
- long_term_fix: every service that mounts `./src` also mounts `./tools:/opt/airflow/tools:ro`. The guard reads `docker-compose.example.yml` and requires the pairing wherever `./src` is mounted, so a new service cannot be added half-equipped. Read-only on purpose: a container that can rewrite the repo's operational scripts is a surprise nobody wants.
- autofix: none
- guard: { type: pytest, ref: tests/test_operational_scripts_are_reachable_in_containers.py }
- rex_ref: tools/create_canary.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: ⚠️ the production `docker-compose.yml` is **gitignored**, so this fix does NOT propagate by `git pull`. The mount has to be added on the server by hand, once. A guard that only reads the versioned example cannot see that — it is checking the template, not the deployment. Named here rather than left implicit.

## finding-rendered-but-not-alerted
- status: fixed
- severity: P1
- kind: deterministic
- symptom: a monitoring check runs, finds a real problem, writes it to xcom — and no alert is ever sent. The dashboard of checks looks complete; the inbox stays empty.
- root_cause: the finding takes part in the email BODY and even the SUBJECT line, but not in the boolean that decides whether to send an email at all. Measured 2026-08-21 in `airflow/dags/alert_monitor.py`: `central_apps_broken` was rendered at line ~794 and placed FIRST in the subject at ~829, while `has_issues` at ~533 listed eight other sources and not it. A shared app that stopped authenticating, as the only problem, produced nothing — the function returned early. It was masked purely by coincidence: Meta happened to be broken *and* stale at once, and staleness was in the decision. The check written specifically to end a months-long silence was itself silent under exactly the condition it targeted.
- signature: `python3 -m pytest tests/test_alert_monitor_sends_what_it_finds.py -q`
- long_term_fix: the guard parses the DAG, collects every local name assigned from an `xcom_pull` inside `send_consolidated_alert`, and requires each to appear in the `has_issues` expression. It sweeps the class rather than the instance, so a check added later gets the same treatment for free.
- autofix: none
- guard: { type: pytest, ref: tests/test_alert_monitor_sends_what_it_finds.py }
- rex_ref: airflow/dags/alert_monitor.py
- first_seen: 2026-08-21
- History:
  - 2026-08-22: widened shape — the existing guard covers *pulled but not decided*, and a state that is never COMPUTED cannot be pulled. `readiness_red_flags` only returned `NO_DATA`, so a tenant who signed up and declared nothing produced no row at all and no alert could exist for the single most likely outcome of a beta invitation. `readiness_stalled_flags` (TODO for more than 7 days, measured from `saas_artists.created_at`) now computes it, and the existing guard caught the new xcom key for free when it was deliberately left out of `has_issues` — verified by mutation.
  - 2026-08-21: found while adding `check_canary_health` — reading the send path to wire a new finding is what exposed that an existing one was never wired. Adding a neighbour is a cheap way to audit the neighbourhood.
  - 2026-08-21: the accompanying wiring guard was ITSELF hollow at first — a `re.search` with `DOTALL` spanning from `t_creds` to `>> t_alert` swept up the operator DEFINITIONS in between, so `t_canary` was "found" even after being removed from the dependency line. Third hollow guard of the same session, third one caught only by mutation. Assert on the narrowest text that carries the meaning, never on "does this name appear somewhere in the file".

## canary-tenant-unwatched
- status: fixed
- severity: P2
- kind: deterministic
- symptom: every global freshness light is green while every real artist collects nothing.
- root_cause: freshness is measured per SOURCE across the fleet, and a source stays fresh as long as ONE tenant collects — which is almost always the admin, whose data path differs from a tenant's. A break in the per-tenant path (a lost identity mirror, a DAG that stops honouring `dag_run.conf`, an isolation regression) is therefore invisible to every existing check. The canary tenant exists precisely to be that second data point, and until 2026-08-21 nothing read it: a watchdog with no reader.
- signature: `python3 -m pytest tests/test_alert_monitor_sends_what_it_finds.py -q`
- long_term_fix: `check_canary_health` in `alert_monitor` reports, per platform the canary actually declared, whether rows are still landing under it (36 h threshold — one nightly cycle plus margin, so a single missed run is not noise). Absence of a canary is itself reported: with none, the detector is simply off, and that must not read as health. The finding reaches the body AND the subject (`🐤 CANARI MUET`) AND `has_issues`.
- autofix: none
- guard: { type: pytest, ref: tests/test_alert_monitor_sends_what_it_finds.py }
- rex_ref: airflow/dags/alert_monitor.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: the detector is exercised directly against a stubbed database — stale, never-collected, absent, healthy, and never-declared — not only checked for being wired. Wiring a detector that never fires is the same decoration in a different place.

## watchdog-becomes-the-noise
- status: fixed
- severity: P3
- kind: deterministic
- symptom: a daily alert email that always contains the same findings, calls for no action, and is therefore skimmed and then ignored — taking the real findings down with it.
- root_cause: a tenant added FOR monitoring is then counted by the tenant-oriented checks as if it were a customer. Measured 2026-08-21, hours after creating the production canary: `check_credentials_all` and `check_onboarding_readiness` both enumerate `get_active_artists()`, so the canary would have emitted "3 missing credentials" (SoundCloud, Meta, Instagram — which it can never declare; Meta demands real ad-account ownership) plus a permanent "connected but no data" for Spotify, whose readiness signal measures an S4A CSV a canary will never have. `missing_creds` is part of the send decision, so this would have forced an email EVERY night, forever, for a tenant in its correct state.
- signature: `python3 -m pytest tests/test_alert_monitor_sends_what_it_finds.py -q`
- long_term_fix: `get_active_artists(exclude_canaries=True)` in the two onboarding-oriented checks only. The flag defaults to **False** deliberately: excluding by default would silently stop the collectors from running for the canary, and a canary nobody collects for is dead weight. The canary's health has its own dedicated check, which asks the single relevant question — is it still collecting what it declared?
- autofix: none
- guard: { type: pytest, ref: tests/test_alert_monitor_sends_what_it_finds.py }
- rex_ref: airflow/dags/alert_monitor.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: self-inflicted, and caught the same evening only by asking "what does the thing I just added do to the checks that already exist?". This repo has now paid the cry-wolf tax three times — the migrate reporter naming four re-run artefacts next to one real error, the schema drift where 24 of 26 differences were `text` vs `varchar`, and this. A detector's value is set by the ratio of its findings that deserve an action, not by the number it produces.

## app-id-confused-with-ad-account-id
- status: fixed
- severity: P2
- kind: heuristic
- symptom: `Error validating application. Cannot get application info due to a system error.` on every Meta call, which reads as "the token expired" — so the investigation goes to the token and never to the app.
- root_cause: `META_APP_ID` held the admin tenant's **ad account** id (`567214713853881`) instead of the **application** id (`2200684950508458`). Both are plain numbers of similar length, they live in adjacent menus of the same Business Settings page (Accounts → Ad accounts vs Accounts → Apps), and no API payload distinguishes them. Measured 2026-08-21, after three separate investigations had blamed the token. The stored token was ALSO wrong in two independent ways — a stray leading `E` from a paste, and `type=USER` where a `SYSTEM_USER` token was required — so each investigation found a real defect and stopped there, without the app credentials ever being tested against the right app.
- signature: `python3 -m pytest tests/test_central_apps_are_monitored.py -q`
- long_term_fix: `check_meta()` probes `GET /{app_id}` with `{app_id}|{secret}` BEFORE anything else and is fatal on failure, printing which of the two failures Graph reported: "no app under that id — an APP id is NOT an AD ACCOUNT id, check Accounts → Apps" versus "app recognised, secret does not match". `.claude/dev-docs/meta-ads-credential-guide.md` documents the three admin variables, where each is read, and its shape.
- autofix: none
- guard: { type: pytest, ref: tests/test_central_apps_are_monitored.py }
- rex_ref: src/utils/central_apps.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: three defects stacked on one integration, each sufficient to break it alone. Finding one and stopping is the trap — a fix that restores nothing means the other layers are still there. Test every layer independently before declaring a cause: app id, then secret, then token shape, then token validity, then token TYPE.
  - 2026-08-21: the guide already stated "System User tokens — not personal user tokens" while production ran a `type=USER` token. A rule written in prose and verified by nothing is a rule the system does not have.

## suppressed-alert-renders-as-health
- status: guarded
- severity: P2
- kind: deterministic
- symptom: an alert correctly suppressed for a source that has nothing to send is then rendered as 🟢 / ✅ by every surface that reads the same flag. "Quiet because there is nothing to collect" and "quiet because everything is fine" become the same green — beside a two-year-old date.
- root_cause: `check_freshness` answers one question with one flag. `stale=False` means "do not fire", and four readers rendered it as health: `airflow_kpi._section_source_status` (🟢 OK), `artist_readiness.platform_status` (which also feeds `readiness_red_flags`, the onboarding view and `tools/artist_preflight.py`), the `✅ Sources OK` footer of `alert_monitor.send_consolidated_alert`, and `airflow/debug_dag/debug_alert_monitor.py` (`✅ OK (16577h)`). The suppression written on 2026-08-21 for Meta Ads — no ACTIVE campaign, so no insight row can exist — therefore converted a nightly false RED into a permanent false GREEN. The second failure is worse: a red that fires every night is eventually read as noise, a green is never questioned at all.
- signature: `python3 -m pytest tests/test_expected_silence.py -q`
- long_term_fix: the suppression carries its measured reason (`expected_silence`) next to the flag, and every surface that renders freshness gained a distinct third state — ⏸️ — that prints that reason. `platform_status` gained a `QUIET` status that outranks the row count but never the missing identity. The guard follows the reason at each hop: the pure status function, the wired readiness matrix, the view's actually-rendered table, the xcom payload, the email footer and the debug script. `stale` alone can no longer be read as "healthy" anywhere.
- autofix: none
- guard: { type: pytest, ref: tests/test_expected_silence.py }
- rex_ref: src/utils/freshness_monitor.py
- first_seen: 2026-08-21
- History:
  - 2026-08-21: found by asking who READS the field the suppression writes — the answer was nobody. Sibling of `finding-rendered-but-not-alerted`, mirrored: there a finding reached the body but not the send decision; here a decision reached the flag but not the reader. Both come from a single boolean carrying two different questions. Six guards, each verified RED by mutation (remove the QUIET branch, the view branch, the reason caption, the footer filter, the xcom key, the debug branch) and green after. The fourth surface — the debug script — was found only by sweeping the class rather than looking at the bug, and it is the worst of the four: it is what someone runs when they already suspect something.

## catalogue-index-omits-its-own-entries
- status: guarded
- severity: P3
- kind: deterministic
- symptom: the Index table at the top of a catalogue stops listing the entries below it. Every reader who scans the index concludes a class does not exist — and catalogues the same defect a second time under a new name.
- root_cause: `.claude/dev-docs/error-classes.md` keeps a hand-maintained Index table while `/capitalise` appends entries at the end of the file. Nothing tied the two together, and nothing failed when they diverged. Measured 2026-08-21: **63** entries, **51** index rows. The twelve missing were the twelve most recent, four of them written the same day.
- signature: `python3 -m pytest tests/test_error_class_index_is_complete.py -q`
- long_term_fix: the guard checks BOTH directions — an entry with no row, and a row whose anchor no longer resolves to an entry (a rename leaves a dead link that reads as catalogued). The twelve missing rows were regenerated from the entries themselves rather than retyped, and `/capitalise` now states the index row as part of what it writes.
- autofix: none
- guard: { type: pytest, ref: tests/test_error_class_index_is_complete.py }
- rex_ref: .claude/commands/capitalise.md
- first_seen: 2026-08-21
- History:
  - 2026-08-21: found while adding a class, not while looking for it. An omission is silent in the one direction that matters: the index never claims to be complete, so its incompleteness cannot contradict anything. Two entries surfaced as a side effect — the two CI-waste classes declare neither `severity` nor `autofix`; their cells are left `—` rather than filled with an invented severity.

## config-corrected-in-the-file-that-loses
- status: guarded
- severity: P2
- kind: manual
- symptom: a credential is investigated, found wrong, and corrected — and nothing changes. Every later look at the corrected file confirms the fix, so the investigation closes and the integration stays broken.
- root_cause: the value lives in two env files and the fix went into the one that does NOT win. `src/utils/env_files.ENV_FILES` loads `.env.local` first with `override=False`, so **the local file wins**; the correction of 2026-08-21 went into `.env`. Measured 2026-08-22: `.env` held the correct app (`2200684950508458`, ETL_DASHBOARD_SPOTIFY) and a valid System User token — 43 scopes, `expires_at=0` — while `.env.local` still held the **ad account** id in `META_APP_ID` and a token carrying one stray pasted `E`. Locally every Meta call had been failing on the fixed configuration for a day, and the roadmap still described R13 as blocked on a human regenerating a token that was already valid.
- signature: `python3 tools/check_central_apps.py`
- long_term_fix: the probe resolves the environment through `load_project_env()` — the same root-anchored, `.env.local`-first order the dashboard and the DAGs use — so it reports on the configuration that actually runs. Run against the live defect it exits 1 and names the cause (`1 extra character ('E') before the 'EAA' prefix`); after removing the stale mirror it exits 0. The duplicate Meta keys were deleted from `.env.local` rather than corrected, so one file owns them.
- autofix: none
- guard: { type: pytest, ref: tests/test_operator_tools_read_the_apps_env.py }
- rex_ref: tools/check_central_apps.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `kind: manual` deliberately. The signature needs the operator's real env files; in CI there are none, the probe skips every platform and exits 0 — vacuously green. What CI *can* guard is that the probe reads the app's environment at all, and that is the pytest above. A signature that cannot fail in CI must not be labelled deterministic just because it is a clean command.
  - 2026-08-22: sibling of `identity-mirrored-but-written-once` one layer down — there an identity in two tables written once, here a secret in two files corrected once. The shape repeats because nothing in either layer says which copy decides.

## same-platform-judged-on-different-tables
- status: guarded
- severity: P2
- kind: deterministic
- symptom: several surfaces each decide whether a platform is "collecting" by reading a different table, so the same tenant is 🟢 on one screen and 🔴 on another — both truthfully. Measured 2026-08-22: Spotify was judged on FOUR tables. An artist who entered their Spotify artist id, passed a connection test that named the artist back to them, and whose `spotify_api_daily` was filling rows normally, still read 🔴 "Connecté — aucune donnée" until they uploaded a CSV. Spotify is the platform onboarding recommends first, so this was most artists' first impression of the product.
- signature: `python3 -m pytest tests/test_platform_sources_agree.py -q`
- root_cause: `src/utils/artist_readiness.py:33` bound the `spotify` key to the single freshness source `"Spotify S4A"` → `s4a_song_timeline`, the CSV **upload** table. `src/utils/freshness_monitor.py` already declared `"Spotify API"` with `tenant_table: track_popularity_history` — the table the DAG actually fills — and no reader consumed it. Meanwhile `alert_monitor.check_canary_health` restated its own pair of tables in a literal list, and `src/dashboard/utils/kpi_helpers.py` restated a third. Four hand-written table lists, one platform.
- long_term_fix: `freshness_monitor.SOURCES_FOR_PLATFORM` is the single registry of which sources can prove a platform, with `tables_for_platform()` derived from it. `artist_readiness` scores every source for a platform and keeps the BEST (an artist who only uploads CSVs and one who only connects the API must both reach 🟢, and neither should be told to do the other's work). The canary watchdog derives its targets and its identifier allowlist from the same registry instead of restating them.
- autofix: none
- guard: { type: pytest, ref: tests/test_platform_sources_agree.py }
- rex_ref: src/utils/freshness_monitor.py
- first_seen: 2026-06-19 (Benken) — surfaced 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by mutation, twice: binding `spotify` back to `("Spotify S4A",)` fails `test_spotify_is_provable_by_the_api_table_and_by_the_csv`; restoring the hardcoded pair in `check_canary_health` fails `test_the_canary_watchdog_hardcodes_no_table`. Green after restoring both. **Not** validated against the pre-fix tree: the registry the guard reads IS the fix, so there it errors on import (exit 2) rather than failing on the defect — the mutation is the honest red, and the distinction is recorded rather than papered over.
- Notes:
  - The watchdog half of the guard is AST, not grep. `check_canary_health`'s own
    comments name `track_popularity_history` and `s4a_song_timeline` in prose,
    explaining this very defect — a textual signature would go red on the
    explanation of its own fix, and the only way to keep CI green would be to stop
    documenting.
  - `kpi_helpers.SOURCES_CONFIG` was deliberately NOT rewritten to derive from
    `MONITOR_TARGETS`: it carries sources readiness has no opinion on (iMusician,
    Apple Music) and feeds a UNION-ALL query with its own allowlists, so a full
    derivation would change runtime behaviour for no gain. On the labels the two
    share they already agreed; the guard pins that agreement instead.

## map-key-unreachable-by-construction
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a config dict carries an entry no caller can ever select. The behaviour it declares never runs, and the file reads as though the feature exists. Measured 2026-08-22: saving an Instagram Business Account ID triggered `meta_ads_api_daily` and never `instagram_daily`, so the artist connected Instagram, saw the toast promising data "in ~2 min", and no first collection ever ran.
- signature: `python3 -m pytest tests/test_credentials_save_triggers_the_right_dag.py -q`
- root_cause: `src/dashboard/views/credentials/_core.py` keyed `_PLATFORM_DAG_MAP` on the form TAB and included an `'instagram'` entry. `_handle_save` is only ever called with a key from `_registry.PLATFORMS`, which has four tabs — `ig_user_id` is a FIELD of the meta tab, not a tab of its own. The lookup `_PLATFORM_DAG_MAP.get(platform_key)` could therefore never return `instagram_daily`.
- long_term_fix: the map is keyed on the LOGICAL platform, and a pure `dags_for_save(tab_key, extra)` returns every DAG whose identity was actually written by this save — so one tab can start several collections, and a blank field starts none. `PLATFORM_TO_DAGS` (the KPI badge map, a third copy) is derived from the same dict.
- autofix: none
- guard: { type: pytest, ref: tests/test_credentials_save_triggers_the_right_dag.py }
- rex_ref: src/dashboard/views/credentials/_core.py
- first_seen: 2026-08-12 (Grinch) — surfaced 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by mutation: restoring the tab-keyed lookup fails 4 of 7 tests, including `test_no_dag_map_key_is_unreachable` — the assertion that would have caught the original entry. Green after restoring. Like its sibling above, the pre-fix tree cannot run this guard (it imports the new map), so the mutation is the validated red.
- Notes:
  - The general shape is worth more than the instance: **an entry keyed in a
    namespace its caller never uses is not "dead code", it is a promise the file
    keeps making.** Nothing errors, nothing logs, and the reader — human or model —
    concludes the feature is wired. The guard asserts reachability, not equality:
    every declared value must be producible from some real caller input.

## guard-derived-from-the-thing-it-guards
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a test is GREEN while the thing it guards is wrong, because it derives its own scope or its own expectation from that thing. Two shapes, both measured 2026-08-22: (a) an assertion that two copies are EQUAL, passing while both are wrong; (b) a parametrised suite whose cases come from the registry under test, so a missing entry removes test cases instead of failing one — the run goes from "N passed" to "N-3 passed", both green.
- signature: `python3 -m pytest tests/test_identity_registry_ratchet.py tests/test_canary_identity_map_is_derived.py -q`
- root_cause: `tests/test_create_canary.py` asserted `create_canary._IDENTITY_FIELD == _core.UNIQUE_IDENTITY_FIELDS`. Both had four entries, both omitted `instagram`, and the assertion therefore **held the gap in place**: adding Instagram to either side alone would have failed the suite. Meanwhile `tests/test_identity_uniqueness.py` parametrised over `UNIQUE_IDENTITY_FIELDS`, so Instagram was never a case. The concrete cost: `find_identity_conflict` returned None for `instagram`, two tenants could claim the same Instagram Business Account with no refusal, and the canary could not exercise the platform that broke in the most recent artist test.
- long_term_fix: `src/utils/tenant_identity.PLATFORM_IDENTITIES` is the single registry; six former copies now derive from it (`_core.UNIQUE_IDENTITY_FIELDS`, `create_canary._IDENTITY_FIELD`, `artist_readiness._identity`, `_core.PLATFORM_TO_DAGS`, `tests/test_identity_fields_collectable`, and the `IDENTITY_KEYS`/`IDENTITY_MIRRORS` views). Against the derivation itself, two things a derived guard cannot do: a **literal ratchet** naming the five platforms in a file of its own, and an **AST assertion that a consumer holds no map literal at all** — which fails on a pasted copy even when the copy happens to be correct.
- autofix: none
- guard: { type: pytest, ref: tests/test_identity_registry_ratchet.py }
- rex_ref: src/utils/tenant_identity.py
- first_seen: 2026-08-12 (Grinch) — named 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by mutation and, more usefully, by the CONTRAST: removing `instagram` from the registry leaves the parametrised uniqueness suite green with fewer cases (8 passed) while the literal ratchet fails. Pasting the old four-entry literal back into `create_canary.py` fails all three derived-map assertions, including the AST one that an equality check could never make.
- Notes:
  - The three pure assertions were moved OUT of `tests/test_create_canary.py`
    into their own file because that module is DB-gated as a whole. They needed no
    database and were invisible on any developer machine without Postgres on 5433 —
    which is precisely the kind of machine where the omission was introduced. A
    guard that only runs in CI is a guard that does not run while the code is
    being written.
  - Sibling of `catalogue-index-omits-its-own-entries`: an omission that
    contradicts nothing. There the index never claimed completeness; here the suite
    never claimed a case count. Both are silent in the one direction that matters.

## broken-probe-rendered-as-user-fault
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a check that FAILED (missing table, bad identifier, dead connection) renders identically to "connected, no data", so the user is told to fix something that is not theirs. They change a working setting and the screen still says red.
- signature: `python3 -m pytest tests/test_broken_probe_is_not_the_artists_fault.py -q`
- root_cause: `src/utils/freshness_monitor.py` sets an `error` field on every failed probe, and its own comment says why: "`stale=True` alone made a BROKEN check look exactly like 'connected but no data'". `src/utils/artist_readiness.py` never read it — it passed `last_dt=None, stale=True` and the status collapsed to `NO_DATA` 🔴 "Connecté — aucune donnée", with a `next_action` telling the artist to check an id that was never the problem. `tools/artist_preflight.py` step 4 inherited the same blindness, so the gate run before an artist session also blamed the tenant.
- long_term_fix: a sixth status `BROKEN` (⚠️), ranked between `TODO` and `NO_DATA` so a failed probe never outranks a source that actually answered and never outranks the tenant's own missing identity. `next_action(BROKEN)` deliberately asks the artist for **nothing**. `readiness_red_flags` returns `NO_DATA` **and** `BROKEN` — both need someone to look, and the action text is what says whose move it is.
- autofix: none
- guard: { type: pytest, ref: tests/test_broken_probe_is_not_the_artists_fault.py }
- rex_ref: src/utils/artist_readiness.py
- first_seen: 2026-06-19 (Benken) — named 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by mutation: neutralising the `if error:` branch fails two cases, including the one asserting a failed probe outranks an expected silence — a measured "nothing to send" is a claim, and a check that broke cannot support it.
- Notes:
  - The field existed, documented, for the exact purpose it was not used for. Worth
    more than the fix: **writing the distinction is not the same as reading it.**
    Same shape as `finding-rendered-but-not-alerted` (a finding reached the body but
    not the send decision) and `suppressed-alert-renders-as-health` (a decision
    reached the flag but not the reader).

## row-existence-read-as-connection
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a surface decides "connected" from the presence of a credentials row rather than from the identity value, so a tab opened and saved blank reads as ✅ — beside a readiness matrix showing ⚪ for the same tenant on the same data.
- signature: `python3 -m pytest tests/test_connected_means_declared.py -q`
- root_cause: four surfaces, four variants of the same shortcut. `credentials/_render.py::_render_global_kpi` used `platform_key in existing`; `views/onboarding.py::_get_configured_platforms` used `{r[0] for r in rows}`; `utils/setup_focus.py::connected_platforms` used `set(rows or {})`; `views/home.py::_section_onboarding` ticked the WHOLE credentials step on `COUNT(*) FROM artist_credentials` — one row, any platform. The Meta row makes it sharper: it carries two identities, so a row holding only `ig_user_id` counted as Meta-connected. And Spotify could manufacture exactly such a row — `_render.py` re-wrote `extra['spotify_artist_id']` after the empty-value pop, making it the one platform able to persist `{"spotify_artist_id": ""}`.
- long_term_fix: `tenant_identity.declared_identities()` — pure, no DB, no Streamlit — is the single answer to "what has this tenant declared", and all four surfaces call it. `home.py` keeps its single round-trip but counts rows carrying a non-empty identity, with the field names bound as a parameter array derived from the registry (never interpolated).
- autofix: none
- guard: { type: pytest, ref: tests/test_connected_means_declared.py }
- rex_ref: src/utils/tenant_identity.py
- first_seen: 2026-08-12 (Grinch) — named 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by mutation on two surfaces: `set(rows or {})` restored in `setup_focus.py`, and the bare `COUNT(*)` restored in `home.py`. A pre-existing test had to be corrected rather than kept: `test_connected_platforms_survives_jsonb_as_text_and_nulls` asserted that a meta row with `extra_config = None`, or unparseable text, counted as Meta-connected. It pinned the defect.
- Notes:
  - The Python half of the guard is AST. The docstrings of the corrected functions
    describe the forbidden expression, because that is how you explain why it is
    gone — a textual sweep would go red on its own explanation.
  - A test can encode a defect and stay green forever. This one had a name, a
    docstring and an edge-case list, and every case asserted the wrong answer.
