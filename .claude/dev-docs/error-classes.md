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
