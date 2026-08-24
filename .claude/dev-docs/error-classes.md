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

<!-- fields-ratchet: 0 -->

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
| [artist-id-or-1](#artist-id-or-1) | P1 | deterministic | guarded | none |
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
| [gate-with-no-test-of-its-own](#gate-with-no-test-of-its-own) | P3 | deterministic | guarded | none |
| [tenant-identity-reaches-a-url-unvalidated](#tenant-identity-reaches-a-url-unvalidated) | P1 | deterministic | guarded | none |
| [secret-in-an-exception-message](#secret-in-an-exception-message) | P1 | deterministic | guarded | none |
| [server-side-render-fetches-tenant-chosen-urls](#server-side-render-fetches-tenant-chosen-urls) | P1 | deterministic | guarded | none |
| [trusted-value-read-from-an-untrusted-header](#trusted-value-read-from-an-untrusted-header) | P1 | deterministic | guarded | none |
| [anonymous-surface-answers-a-private-question](#anonymous-surface-answers-a-private-question) | P1 | deterministic | guarded | none |
| [revocation-written-but-never-read](#revocation-written-but-never-read) | P1 | deterministic | guarded | none |
| [sentinel-means-privileged-and-missing](#sentinel-means-privileged-and-missing) | P2 | deterministic | guarded | none |
| [pipeline-writes-to-the-copy-nobody-reads](#pipeline-writes-to-the-copy-nobody-reads) | P2 | deterministic | guarded | none |
| [decision-made-on-a-string-truncated-for-display](#decision-made-on-a-string-truncated-for-display) | P2 | deterministic | guarded | none |
| [per-tenant-outcome-not-recorded](#per-tenant-outcome-not-recorded) | P2 | deterministic | guarded | none |
| [stopped-collecting-is-not-a-status-anyone-reads](#stopped-collecting-is-not-a-status-anyone-reads) | P2 | deterministic | guarded | none |
| [mandatory-filter-with-no-guard](#mandatory-filter-with-no-guard) | P2 | deterministic | guarded | none |
| [detector-with-no-scheduler](#detector-with-no-scheduler) | P2 | deterministic | guarded | none |
| [script-replaced-while-it-runs](#script-replaced-while-it-runs) | P2 | manual | reported | none |
| [test-leaves-a-hole-in-sys-modules](#test-leaves-a-hole-in-sys-modules) | P2 | deterministic | guarded | none |
| [second-factor-budget-refunded-by-the-first](#second-factor-budget-refunded-by-the-first) | P2 | deterministic | guarded | none |
| [guard-scope-is-a-hand-written-list](#guard-scope-is-a-hand-written-list) | P2 | deterministic | guarded | none |
| [input-nobody-would-type-reaches-the-driver](#input-nobody-would-type-reaches-the-driver) | P3 | deterministic | guarded | none |
| [repo-copy-of-a-config-is-not-what-runs](#repo-copy-of-a-config-is-not-what-runs) | P2 | deterministic | guarded | none |
| [resave-erases-a-secret-the-form-cannot-show](#resave-erases-a-secret-the-form-cannot-show) | P1 | deterministic | guarded | none |
| [delivery-failure-logged-as-success](#delivery-failure-logged-as-success) | P1 | deterministic | guarded | none |
| [static-hint-contradicts-the-live-probe](#static-hint-contradicts-the-live-probe) | P2 | deterministic | guarded | none |
| [detector-written-and-never-called](#detector-written-and-never-called) | P2 | deterministic | guarded | none |
| [age-computed-against-another-clock](#age-computed-against-another-clock) | P2 | deterministic | guarded | none |
| [audit-scope-restated-not-derived](#audit-scope-restated-not-derived) | P2 | deterministic | guarded | none |
| [upsert-freezes-its-own-timestamp](#upsert-freezes-its-own-timestamp) | P2 | deterministic | guarded | none |
| [two-doors-onto-one-database](#two-doors-onto-one-database) | P2 | deterministic | guarded | none |
| [unmeasured-rendered-as-measured](#unmeasured-rendered-as-measured) | P2 | deterministic | guarded | none |
| [config-corrected-in-the-file-that-loses](#config-corrected-in-the-file-that-loses) | P2 | manual | guarded | none |
| [tool-imports-the-app-without-a-path](#tool-imports-the-app-without-a-path) | P1 | deterministic | guarded | none |
| [test-sends-real-mail-to-real-people](#test-sends-real-mail-to-real-people) | P1 | deterministic | guarded | none |
| [unattributable-payment-link](#unattributable-payment-link) | P2 | deterministic | guarded | none |
| [partial-collection-invisible](#partial-collection-invisible) | P2 | deterministic | guarded | none |
| [test-calls-a-real-api](#test-calls-a-real-api) | P2 | deterministic | guarded | none |
| [sender-identity-composed-twice](#sender-identity-composed-twice) | P3 | deterministic | guarded | none |
| [traceback-rendered-to-the-visitor](#traceback-rendered-to-the-visitor) | P2 | deterministic | guarded | none |
| [boundary-narrower-than-the-surface](#boundary-narrower-than-the-surface) | P2 | deterministic | guarded | none |
| [two-surfaces-two-truths](#two-surfaces-two-truths) | P2 | deterministic | guarded | none |
| [success-message-outside-its-condition](#success-message-outside-its-condition) | P2 | deterministic | guarded | none |
| [the-page-that-tells-you-what-to-do-is-unreachable](#the-page-that-tells-you-what-to-do-is-unreachable) | P2 | deterministic | guarded | none |
| [dead-content-that-still-ships](#dead-content-that-still-ships) | P2 | deterministic | guarded | none |
| [the-feature-is-wired-to-the-function-nobody-calls](#the-feature-is-wired-to-the-function-nobody-calls) | P3 | deterministic | guarded | none |
| [the-feature-exists-and-the-path-never-reaches-it](#the-feature-exists-and-the-path-never-reaches-it) | P2 | deterministic | guarded | none |
| [detect-then-reject-with-the-wrong-advice](#detect-then-reject-with-the-wrong-advice) | P3 | deterministic | guarded | none |
| [too-many-charts-competing-for-one-decision](#too-many-charts-competing-for-one-decision) | P3 | deterministic | guarded | none |
| [prune-scoped-wider-than-what-it-refreshed](#prune-scoped-wider-than-what-it-refreshed) | P1 | deterministic | guarded | none |
| [layer-written-but-never-wired](#layer-written-but-never-wired) | P2 | deterministic | guarded | none |
| [absence-rendered-as-a-measurement](#absence-rendered-as-a-measurement) | P2 | deterministic | guarded | none |
| [counter-includes-our-own-robots](#counter-includes-our-own-robots) | P3 | deterministic | guarded | none |
| [leak-via-an-exception-received-as-an-argument](#leak-via-an-exception-received-as-an-argument) | P2 | deterministic | guarded | none |
| [format-marker-in-a-plain-string](#format-marker-in-a-plain-string) | P2 | deterministic | guarded | none |
| [audit-reads-the-constraints-not-the-installed-set](#audit-reads-the-constraints-not-the-installed-set) | P3 | deterministic | guarded | none |
| [validation-bound-invented-not-read-from-the-schema](#validation-bound-invented-not-read-from-the-schema) | P2 | deterministic | guarded | none |
| [empty-table-rendered-as-health](#empty-table-rendered-as-health) | P3 | deterministic | guarded | none |
| [guard-seeded-by-prose-not-by-code](#guard-seeded-by-prose-not-by-code) | P3 | deterministic | guarded | none |
| [boundary-with-no-named-exit-kills-what-must-pass](#boundary-with-no-named-exit-kills-what-must-pass) | P2 | deterministic | guarded | none |
| [dead-argument-from-a-major-version-ago](#dead-argument-from-a-major-version-ago) | P2 | deterministic | guarded | none |
| [session-wide-stub-of-an-installed-package](#session-wide-stub-of-an-installed-package) | P2 | deterministic | guarded | none |

> A `—` cell means the entry itself declares no such field. The two CI-waste classes
> arrived from another repo in a looser format; no severity has been invented for them.

---

## streamlit-pin-drift
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a package pinned `==X` in one manifest while another manifest / the lockfile / the installed env pins `==Y` → prod≠dev, "works locally breaks in Docker".
- signature: `python3 tools/dev/check_manifest_consistency.py`
- root_cause: three manifests (`pyproject.toml`, `requirements.txt`, `uv.lock`) each state the same pin, and nothing compared them — the Dockerfile installs from one, the dev venv from another.
- long_term_fix: one manifest is canonical (`pyproject.toml`) and the others are DERIVED from it; until they are, `check_manifest_consistency.py` blocking in CI is the fix.
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
- root_cause: a Make recipe is a list of commands with no declared preconditions, so the first line that needs Docker discovers it is absent halfway through the target.
- long_term_fix: every runtime target declares a prerequisite target that probes its dependency and exits 1 naming the fix command — the `dashboard: check-env` shape (rule #10).
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
- root_cause: `except Exception: return []` reads as defensive programming and is indistinguishable, from the DAG's point of view, from a real empty result — an upstream 401 and a genuinely empty account produce the same SUCCESS.
- long_term_fix: collectors raise (CLAUDE.md rule #6) and the AST audit blocks in CI, so 'no rows' can only mean the API said so.
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
- root_cause: `get_artist_id()` returns None for two unrelated states (admin, and no tenant), and `or 1` was the shortest way to make a view render during development.
- long_term_fix: `view_session()` and `tenant_scope()` (R25) encapsulate the guard, so a view cannot express the fallback without going out of its way.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_tenant_scoped_action_names_its_tenant.py::test_a_missing_tenant_never_falls_back_to_a_hardcoded_one }
- rex_ref: CLAUDE.md
- first_seen: 2026-03-27 (ref: DEVLOG#2026-03-27)
- History:
  - 2026-03-27: 9 views fixed with explicit guard. Pattern still ungrepped in CI until now.
  - 2026-05-15: catalogued, added to `make audit`.
  - 2026-05-15: no-arg /sweep caught a FALSE POSITIVE — the prior signature `get_artist_id() *or *1` matched the `view_session()` docstring + CLAUDE.md rule text that *quote* the anti-pattern, breaking the `deterministic` (CI-safe) contract. Hardened to require assignment context `= get_artist_id() or 1` (verified 0 real hits, docstring excluded). `make audit` recipe synced to the same regex (no catalogue↔audit drift).
  - 2026-06-13: **now CI-BLOCKING** — `audit_runner.py --deterministic` runs every `kind: deterministic` signature as a blocking ci.yml step (0 real hits today). status open→guarded; this P1 leak pattern can no longer merge.
  - 2026-08-23: gardée pour la première fois, dans le cadre de R40. La classe était cataloguée P1 depuis des mois avec `status: open` et `guard: none` — le catalogue la connaissait, rien ne la surveillait. Le garde lit l'AST : un `BoolOp(Or)` dont la première valeur est `get_artist_id()` / `tenant_scope()` et une autre une constante. Vu rouge par mutation sur `get_artist_id() or 1` et `tenant_scope() or 'admin'`, vert sur le dépôt réel.


## sql-fstring-identifier
- status: open
- severity: P1
- kind: heuristic
- symptom: a table/column name interpolated into SQL via f-string without `frozenset` allowlist validation (CLAUDE.md rule #8) → SQL injection.
- signature: `! grep -rnE "f\"\"\"?[^\"]*(FROM|JOIN|INTO|UPDATE|TABLE) +\{" src/ --include=*.py`
- root_cause: psycopg2 parameterises VALUES but not identifiers, so a dynamic table or column name has no `%s` form and the f-string is the only thing that works.
- long_term_fix: every dynamic identifier resolves through a `frozenset` allowlist before interpolation (rule #8); the allowlist is the fix, the grep only finds the ones that skipped it.
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
- root_cause: a helper called from a view opens its own connection because it cannot see the caller's — the cost is invisible in dev where the pool is idle.
- long_term_fix: `view_session()` yields the one connection, and helpers take `db` as a parameter instead of resolving it.
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
- root_cause: `datetime.now()` is the obvious spelling and is correct for cosmetic use, so the same call is right in an email body and wrong two lines later in an upsert payload.
- long_term_fix: `.claude/rules/python.md` splits the two by destination: anything persisted or returned by the API uses `datetime.now(timezone.utc)`. A repo-wide ban would break the legitimate cosmetic uses.
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
- root_cause: `Styler.format` raises on None rather than rendering an empty cell, and the NULL only appears when a LEFT JOIN misses — which dev data usually does not.
- long_term_fix: the PostToolUse hook rejects a `.style.format(` with no `na_rep=` at edit time, before the view is ever rendered.
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
- root_cause: the write allowlist in `postgres_handler.py` and the tables a collector writes are two lists maintained by different people at different times.
- long_term_fix: `tests/test_allowed_tables_coverage.py` derives one from the other and fails on divergence, so adding a table to a collector fails CI until it is registered.
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
- root_cause: the manual four-line guard predates `view_session()` and is still correct, so nothing forces a rewrite — and every copy of it is a fresh chance to drop the `is_admin()` line. R25 found nine views that had.
- long_term_fix: migrate the remaining views to `view_session()`; the class closes when no view holds its own copy of the guard.
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
- root_cause: psycopg2 returns `datetime.date` for a DATE column while `pd.to_datetime` produces `pd.Timestamp`, and the two compare fine until a sort or a merge puts them side by side.
- long_term_fix: normalise at the boundary — every date leaving a query goes through `pd.to_datetime` before it reaches view code.
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
- root_cause: shipping code and running it are separate events here: `src/` is volume-mounted so the code is live instantly, while the table only fills on the DAG's next schedule.
- long_term_fix: the freshness monitor reports a table that exists with zero rows as a collection gap rather than as no data — an empty table with a live DAG is a state the dashboard must name, not render as a blank chart.
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
- root_cause: `collected_at` is present on every table and a release date is not, so it is the column at hand when a default entity has to be picked.
- long_term_fix: `EntitySpec` carries an explicit `release_column`; ordering by ingest time is then a choice someone had to write, not the default.
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
- root_cause: operator-facing prose is not executed by anything, so a script rename or an auth-model change leaves it behind with no test going red.
- long_term_fix: every command named in operator text is either a real path this signature checks, or the text names the surface instead of the script.
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
- root_cause: a numeric column with one NULL loads as pandas `object`, and `.round()` on object dtype raises rather than coercing — so the crash needs both a NULL and that specific call.
- long_term_fix: `pd.to_numeric(..., errors='coerce')` at the query boundary; the render-smoke suite against the live DB is what makes the NULL show up before a user does.
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
- root_cause: the same column holds rows written before and after the UTC-aware convention landed, so the mix is in the DATA and no amount of new code removes it.
- long_term_fix: `pd.to_datetime(..., utc=True)` everywhere, plus the aware-timestamp rule in `.claude/rules/python.md` so the data stops growing new naive rows.
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
- root_cause: the hygiene hooks are correct for source files and wrong for byte-exact fixtures, and they run on everything staged.
- long_term_fix: `^tests/fixtures/` is excluded from the reflowing hooks in `.pre-commit-config.yaml`.
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
- root_cause: S4A replaces `< > : " / \ | ? *` with `_` in export FILENAMES, so the same song arrives spelled two ways depending on whether it came from a file or an API.
- long_term_fix: `canonical_song()` / `canonical_song_sql()` in `src/utils/track_matching.py` — one normalisation both sides call, rather than each join inventing its own.
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
- root_cause: `t(key, french_default)` renders the French default when EN is missing, so an untranslated key is a working page — nothing fails.
- long_term_fix: the CI test enumerates every `t()`/`_t()` call site and requires an EN entry, turning a silent fallback into a red build.
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
- root_cause: `test_api.py` mocks the database, so a router can SELECT a column that no longer exists and still pass every test it has.
- long_term_fix: `tests/test_api_db_smoke.py` hits every data endpoint against the real schema; a mocked suite alone cannot see this class.
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
- root_cause: a spreadsheet treats a leading `=`, `+`, `-` or `@` as a formula, and our exports pass through names the tenant typed.
- long_term_fix: every export goes through `defang_formulas()` in `csv_exporter.py`; the export helper is the only writer, so a new export inherits it.
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
- root_cause: `config.yaml` exists in dev and not in prod, so `config['x']` is correct on the machine where the code is written and a `KeyError` on the machine where it runs.
- long_term_fix: env-first resolution with config.yaml as the local fallback (the `_smtp_config()` shape), so the dev path is the exceptional one.
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
- root_cause: a hotfix applied straight to the production database has no file to review, and nothing compared the two schemas until someone tried a fresh install.
- long_term_fix: `make sync-check` in the deploy path plus the `schema_migrations` ledger (migration 071), so prod can only reach a state the repo can rebuild.
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
- root_cause: a DAG written when there was one tenant reads correctly as a loop; the missing per-iteration try only becomes a fleet outage once a second tenant exists.
- long_term_fix: `tests/test_dag_fleet_isolation.py` requires every artist loop touching `db` to be try-wrapped, and the CI seeds two tenants so single-tenant reasoning cannot pass.
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
- root_cause: `load_dotenv()` at module scope runs at IMPORT, so a file-permission problem becomes an unimportable module rather than a handled error.
- long_term_fix: the guarded-import test forbids an unwrapped module-level `load_dotenv` in `src/collectors/`; the env is loaded from a helper that tolerates an unreadable file.
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
  - 2026-08-22: **`reported` → `guarded`, `manual` → `deterministic`.** `--require` existed since 2026-08-20 and was reachable only by a human typing it. The NIGHTLY path called the bare probes, which return True on absent env by design — correct for a partial deployment, blind in production. Absence is now red inside `alert_monitor.check_central_apps` before any probe runs, and the preflight narrows the absence check to its scope instead of skipping it. New signature: `python3 -m pytest tests/test_central_apps_are_monitored.py -q`, which no longer needs the operator's real env file.
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
  - 2026-08-22: **caught in production, by walking into it.** Deriving the canary watchdog's targets from the freshness registry, I returned both a target's global table and its `tenant_table`. For Spotify that included `artists`, where the column named `artist_id` is the SPOTIFY id (VARCHAR) — the tenant there is `saas_artist_id`. The nightly check answered `operator does not exist: character varying = integer`. It reported "could not run" rather than health (the conservative contract held) but still put a false 🐤 CANARI MUET in the alert subject. `tables_for_platform` now returns the `tenant_table` when a target declares one and never both, guarded by `tests/test_platform_sources_agree.py::test_no_platform_resolves_to_a_table_that_is_not_tenant_scopable`. The class was already catalogued and already in `rules/python.md`; knowing it did not prevent it — a guard did, one commit later than it should have.
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
  - 2026-08-22: the reader existed and watched 2 platforms of 5, on a table that differed from the one the artist's own screen reads. Both fixed: `check_canary_health` derives its targets from `freshness_monitor.SOURCES_FOR_PLATFORM`, and a second reader, `check_canary_preflight`, runs the artist-session gate itself every night — scoped to the platforms the canary declares rather than the hardcoded `youtube` the runbook documents.
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
  - 2026-08-22: nearly reintroduced. Widening the canary watchdog from two hardcoded tables to every table of every declared platform made it demand rows in ALL of them — and Spotify is provable by the API table OR the S4A CSV. The production canary holds 10 rows in `track_popularity_history` and 0 in `s4a_song_timeline`, so a tenant collecting exactly as designed was reported mute. Fixed to a per-platform "at least one table is fresh" verdict, the same best-of-sources rule the artist's own matrix uses. Found by running the DAG in production rather than by reading it.
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

## gate-with-no-test-of-its-own
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a tool whose entire job is to answer go/no-go has no test and no schedule. Its greenness is trusted by a runbook, its logic is verified by nobody, and it only runs when a human remembers — so it reports on the days you did not need it.
- signature: `python3 -m pytest tests/test_artist_preflight.py -q`
- root_cause: `tools/artist_preflight.py` is what stands between a broken tenant and a real artist ("on n'invite personne tant que `make artist-preflight` n'est pas vert"). `grep artist_preflight` found only `Makefile:71`, two test allowlists and prose: no CI job, no cron, no test. Its scope logic was unverified — including the branch that made `--platforms` **skip** the central-app absence check entirely, while the documented production invocation is `--platforms youtube`. The standing production verification therefore proved one platform out of five and never ran the check aimed at the beta failure.
- long_term_fix: `tests/test_artist_preflight.py` pins the behaviours the docstrings claim (typo → exit 2, empty scope → exit 2, QUIET counts as good, BROKEN reds the gate, out-of-scope never gates but is always printed, a raising probe is a red verdict not a traceback). Absence is **narrowed** to the scope instead of skipped. And `alert_monitor.check_canary_preflight` runs steps 2-4 against the canary every night, scoped to the platforms the canary actually declares — computed, not hardcoded.
- autofix: none
- guard: { type: pytest, ref: tests/test_artist_preflight.py }
- rex_ref: tools/artist_preflight.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by mutation: restoring the skip-absence-when-scoped branch fails `test_a_scoped_run_still_requires_its_own_platform`; making `QUIET` no longer count as good fails `test_quiet_counts_as_good`. The scheduled half is guarded for free — `tests/test_alert_monitor_sends_what_it_finds.py` requires every pulled xcom key to take part in `has_issues`.
- Notes:
  - The scheduled version imports the tool's step functions rather than
    reimplementing them. Duplicating the gate's logic to schedule it would recreate
    the class the whole session was about.

## tenant-identity-reaches-a-url-unvalidated
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a free-text field a tenant controls is interpolated into a REST path, and the raw response is echoed back to them. `requests` does not percent-encode `/` in a path you build yourself, so the tenant chooses the endpoint — while the call carries the PLATFORM's shared credential.
- signature: `python3 -m pytest tests/test_credentials_security.py -q`
- root_cause: `ig_user_id` is a plain `st.text_input` (`_registry.py`) saved with no format check, and `_probe_instagram` built `f'{META_GRAPH_BASE_URL}/{ig_user_id}'` with `params={'access_token': <SYSTEM USER TOKEN>}`. Setting it to `me/accounts` produced `https://graph.facebook.com/v24.0/me/accounts?access_token=…`; the 200-with-no-`username` branch then returned `ri.text[:150]` — and `/me/accounts` answers with Page access tokens minted from that System User token, rendered to a non-admin by `st.error`. Verified 2026-08-22 that `requests` leaves the `/` unencoded.
- long_term_fix: the identity registry gained a `pattern` per platform and `identity_is_well_formed()` / `malformed_identities()`; the save path refuses a malformed value before writing, and every probe refuses before the network. `re.fullmatch`, never `match` — `match` accepts `123/me/accounts`, which is the whole attack. No probe echoes a raw response body any more.
- autofix: none
- guard: { type: pytest, ref: tests/test_credentials_security.py }
- rex_ref: src/utils/tenant_identity.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: found by a security audit of the same session's changes, ordered because the session touched secret reads (cross-cutting rule 13). Verified RED by mutation (remove the shape check → the probe accepts `me/accounts` again). The extraction of `_probe_instagram` this session did not create the interpolation — it inherited it — but it DID wire it into `CONNECTION_TESTS`, so the nightly scheduler and the preflight now call it too.
- Notes:
  - The shape rule lives in the identity registry, not in the probe. Five
    platforms, five patterns, one place — otherwise the next probe re-derives
    "what does an id look like" and gets it wrong for the sixth.
  - `account_id` had the same interpolation, constrained by a forced `act_`
    prefix. "Probably safe because of a prefix" is not a control; it is validated
    too.

## secret-in-an-exception-message
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a credential is passed as a QUERY PARAMETER, so a `requests` exception message embeds the full prepared URL. Surfacing the exception — to a user, or into a log — surfaces the credential. No attacker action required: a DNS blip is enough.
- signature: `python3 -m pytest tests/test_credentials_security.py -q -k exception`
- root_cause: two shapes. (a) `src/utils/central_apps.py::check_meta` printed `f"probe error ({exc})"` for a call carrying `META_ACCESS_TOKEN` and `META_APP_ID|META_APP_SECRET` in the query string — executed **nightly** by `alert_monitor.check_central_apps`, whose stdout is persisted in the Airflow task log. (b) the Meta, YouTube, Spotify and SoundCloud connection tests each ended in `except Exception as e: return False, str(e)`, rendered untruncated to the tenant by `st.error`. Meta and YouTube put their credential in the URL, so a non-admin could be shown the platform-wide System User token or the billable API key.
- long_term_fix: no probe surfaces a caught exception; they return `type(e).__name__` plus a static message. Applied uniformly to all four platforms even though Spotify (header auth) and SoundCloud (POST body) are clean today — so nobody has to re-derive which one is safe. The guard walks the AST of every except-handler in those modules and fails on `str(e)` or `f"{e}"`.
- autofix: none
- guard: { type: pytest, ref: tests/test_credentials_security.py }
- rex_ref: src/utils/central_apps.py
- first_seen: 2026-08-22
- History:
  - 2026-08-23: **the guard's scope was the defect a THIRD time, and the rule changed because of it.** Found in production: `youtube_daily` wrote the YouTube API key in clear into the Airflow task log every night. Two independent misses. (a) `src/utils/retry.py` was *inside* the scope and green, because the walk only looked inside `ast.ExceptHandler` — retry does `last_exc = exc` and renders `{last_exc}` **outside** the handler, after the loop. The detector now seeds on every `except … as NAME` and follows plain `alias = NAME` rebindings to a fixpoint. (b) `airflow/dags/` was not in the scope at all, and the question the scope asked — *does this module call an HTTP client?* — is the wrong one: a DAG calls none, it CATCHES AND LOGS the exception the collector raised. The scope is now the **transitive closure of the import graph**: a module is in scope if it calls an HTTP client, or imports one that does. That widening turned up **16 modules and 64 sites**, all fixed by routing through `safe_error`. The resulting invariant is simpler than the old one and needs no judgment call: *never interpolate a raw exception, anywhere* — `safe_error` keeps the message shape and blanks only credential values, so there is no diagnostic cost to applying it everywhere. `airflow/dags/meta_token_refresh.py` was the worst of the 64: its `failed` list is joined into a **raised** exception, which becomes the DAG-failure alert **email**, and a Meta token exchange carries `client_secret` and `fb_exchange_token` in the query string.
  - 2026-08-22: **the guard's own scope was the defect.** Written the same day, it was parametrised over five files named by hand — the four connection probes and `central_apps` — and a full-application audit then found the identical leak in every COLLECTOR, which was in none of them (`instagram_api_collector` sends `client_secret` and `fb_exchange_token` as query params; `youtube_collector` logs `HttpError`, whose repr embeds the URI). The scope is now DERIVED from the tree: every module that both calls an HTTP client and handles an exception. That widening immediately caught four more modules. Sites are fixed with `src/utils/safe_error.py::redact`, which keeps the message shape and blanks the values — blanking the whole message costs the operator the one line that says what broke.
  - 2026-08-22: the guard, written for the four sites the audit named, immediately found **five more** — three in `central_apps` (Spotify/YouTube/SoundCloud) and two raw-body echoes in `_platform_meta`. Verified RED by mutation (restore `str(e)` in the YouTube probe).
- Notes:
  - The nightly one is the worse of the two. A tenant-facing leak needs a person
    clicking during an outage; the log one writes both secrets to disk on its own
    schedule, and the file outlives the incident.

## server-side-render-fetches-tenant-chosen-urls
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a renderer that runs on the SERVER builds a document from tenant data and then resolves the resources it references. Any markup surviving into that document becomes a request made by the server, from inside the network, with the server's own reachability.
- signature: `python3 -m pytest tests/test_pdf_export_cannot_fetch.py -q`
- root_cause: `src/dashboard/utils/pdf_exporter/_report.py` called `HTML(string=html_str).write_pdf()` with no `url_fetcher`. WeasyPrint's default fetcher registers http/https/ftp/**file** with `allowed_protocols=None` and follows redirects. `_renderers.py` escaped nothing (zero occurrences of `escape`), and two tenant-controlled values reach it: a song name — taken from the STEM OF AN UPLOADED CSV FILENAME, and `parse_timeline` does not run it through `canonical_song()` unlike `parse_songs_global` — and a Meta campaign name. Both are free-plan reachable (`export_pdf` and `upload_csv` are in `_FREE_FEATURES`).
- long_term_fix: two independent controls, because either alone is one mistake from failing. `_no_remote_resources` serves `data:` URIs only, so the class is closed whatever future value slips through unescaped; and `_esc()` escapes the three tenant-controlled interpolations the audit named. Deliberately NOT a blanket escape of the file — it also interpolates markup it builds itself (badges, probability bars, row blocks), and escaping those breaks the render. That was tried; the golden-snapshot test caught it.
- autofix: none
- guard: { type: pytest, ref: tests/test_pdf_export_cannot_fetch.py }
- rex_ref: src/dashboard/utils/pdf_exporter/_report.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: found by a full-application audit. Escalation worth noting: `export_pdf.py` lets an ADMIN generate any tenant's report, so a planted payload fires in the admin's session. Verified RED by mutation (remove the `url_fetcher`; un-escape the song title).
- Notes:
  - The golden-snapshot test earned its keep here. A blanket escape looked correct,
    passed a reading, and silently turned every badge into visible `&lt;span&gt;`.
    Byte-identical output is the only assertion that catches a change that is
    invisible in review.

## trusted-value-read-from-an-untrusted-header
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a security control keys on a value taken from a request header the caller controls, so the caller varies the key and the control never fires. It looks present in code review and in the logs.
- signature: `python3 -m pytest tests/test_rate_limit_client_ip.py -q`
- root_cause: `src/api/security.py::client_ip` returned `X-Forwarded-For.split(",")[0]` — the FIRST hop, i.e. whatever the client sent. Cloudflare and Caddy both APPEND the peer they saw, so an attacker-supplied entry survives at position 0. Every rate-limit bucket was therefore caller-chosen.
- long_term_fix: read from the RIGHT (`hops[len(hops) - TRUSTED_PROXY_HOPS]`), prefer Cloudflare's own `CF-Connecting-IP`, and — the part that is easy to get wrong — fall back to the socket peer when there are FEWER hops than expected, because that means the header did not come through our proxies at all. Taking `hops[0]` in that branch restores the bypass in any environment with one proxy instead of two.
- autofix: none
- guard: { type: pytest, ref: tests/test_rate_limit_client_ip.py }
- rex_ref: src/api/security.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. The load-bearing test is `test_the_key_cannot_be_varied_by_the_caller` — 50 crafted requests must collapse to ONE bucket. Asserting "the right IP is returned" would have passed on the first fix attempt, which still trusted a lone spoofed hop. Verified RED by mutation.
- Notes:
  - The damage is not the limiter alone. Chained with the registration oracle
    (`register.py` answers "L'email 'x' est déjà enregistré") and the 5-attempt
    lockout — whose column is shared between the API and the dashboard — an
    anonymous caller could keep every tenant locked out of both, indefinitely.

## anonymous-surface-answers-a-private-question
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a page reachable without authentication behaves differently depending on private state, so a visitor reads that state one request at a time. The page looks correct: every individual message is true and helpful.
- signature: `python3 -m pytest tests/test_registration_is_not_an_oracle.py -q`
- root_cause: `src/dashboard/views/register.py` was written for the honest user and every branch was helpful to them — "L'email 'x' est déjà enregistré" (`:332`), "Le code n'est pas valide" returned BEFORE the account was created (`:344-351`), and `st.error(...{e})` on the psycopg2 message (`:408`). Each is the right thing to tell someone who owns the address. None of them asks whether the person reading owns it.
- long_term_fix: one `_render_success()` for both outcomes, so the two branches cannot drift apart by editing only one; code validation moved AFTER account creation, so a probe costs a full registration instead of a request; a per-IP budget (`src/dashboard/utils/throttle.py`) in front of everything that writes a row or sends a mail; and `public_error_ref()`, which logs the exception under a random 8-hex reference and shows only the reference.
- autofix: none
- guard: { type: pytest, ref: tests/test_registration_is_not_an_oracle.py }
- rex_ref: src/dashboard/views/register.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. The test compares the RENDERED output of two submits byte for byte, normalising only the address the visitor typed, an incident reference and a Retry-After count. Verified RED on each of the four restored behaviours. Its own first version passed on a rejected password — two identical validation errors also compare equal — so it now asserts the fresh submit reached the success path before comparing.

## revocation-written-but-never-read
- status: guarded
- severity: P1
- kind: deterministic
- symptom: an administrative gesture that is supposed to cut access writes a column nothing reads on the live path. The UI confirms, the row changes, and the holder keeps working until their session expires on its own.
- signature: `python3 -m pytest tests/test_revocation_actually_revokes.py -q`
- root_cause: `active` appeared in exactly one query — the login one. `require_login()` (`src/dashboard/auth.py`) returned True from `st.session_state` alone, and the API's `get_current_user` asked only whether the JWT verified. So `admin.py:_toggle_user_active` stopped the NEXT login and nothing else, and changing a password after a compromise left the intruder's 24 h token valid.
- long_term_fix: authorisation is re-read from the row on every request — `active`, `role` and `artist_id`, throttled to 30 s on the dashboard and per-request on the API — plus `saas_users.token_version` (migration 072) carried as a `tv` claim and bumped by deactivation and by a password change. A missing claim reads as 0, so deploying it signs nobody out. The two surfaces fail in OPPOSITE directions on a database outage, deliberately: the dashboard open (a blip must not evict every artist, and it shows a banner), the API closed (its tokens travel further and it has no banner).
- autofix: none
- guard: { type: pytest, ref: tests/test_revocation_actually_revokes.py }
- rex_ref: src/api/deps.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by neutralising the two reads. The suite pins the legacy-token case too — without it, the obvious implementation (reject any token with no `tv`) would have logged out every live user on deploy.

## sentinel-means-privileged-and-missing
- status: guarded
- severity: P2
- kind: deterministic
- symptom: one sentinel value carries two unrelated meanings — "this caller may see everything" and "this caller has no scope" — so the branch written for the first is taken by the second. Every call site is asked to remember the disambiguation, and the ones that forget read as ordinary code.
- signature: `python3 -m pytest tests/test_stray_session_reads_nothing.py -q`
- root_cause: `get_artist_id()` returns None for an admin and None for a session with no tenant, and has said in its own docstring since it was written that callers must separate the two with `is_admin()`. Nine views and `artist_id_sql_filter()` did not — and that last one is how ~30 views reach the database, so its empty filter fragment meant "read every tenant".
- long_term_fix: `tenant_scope()` in `src/dashboard/auth.py` is the disambiguation, once: it returns the tenant, returns None only for a proven admin, and stops the session otherwise. Call sites ask it instead of remembering a two-line guard. The distinct-but-adjacent `artist-id-or-1` class covers the `or 1` spelling; this one covers `is None` read as "admin".
- autofix: none
- guard: { type: pytest, ref: tests/test_stray_session_reads_nothing.py }
- rex_ref: src/dashboard/auth.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. The guard SPIES ON THE QUERIES (`tests/query_spy.py`) rather than on the message: its first version required the string "Session invalide" and failed `upload_csv`, which refuses the session correctly in its own words. Verified RED on eleven views by restoring the pre-fix guards. Every view currently refuses before its first query, so each case also asserts the view rendered something — otherwise "zero unscoped reads" is indistinguishable from "the view never ran".

## second-factor-budget-refunded-by-the-first
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a multi-factor flow rate-limits each step, and the earlier step's success resets the later step's budget. The attacker holds the earlier factor by assumption, so the later one has no budget at all.
- signature: `python3 -m pytest tests/test_second_factor_is_not_brute_forceable.py -q`
- root_cause: two independent causes had to be fixed together. `_authenticate_user` cleared `failed_login_attempts` as soon as the password verified — correct for a password-only login, and the whole exploit when a code was still owed. And the only counter the TOTP challenge touched, `_rate_record_failure()`, lives in `st.session_state`, which a new browser tab resets; since the attacker knows the password, reforging `_totp_pending` in a fresh tab cost one request.
- long_term_fix: the account-level reset moves to AFTER the last factor; a wrong code increments `failed_login_attempts` like a wrong password; and the challenge's budget is keyed by client IP in module state (`src/dashboard/utils/throttle.py`), which a new session does not reset. The per-IP budget also covers the login form, where a per-account lockout never fires at all — password spraying tries one password across many accounts.
- autofix: none
- guard: { type: pytest, ref: tests/test_second_factor_is_not_brute_forceable.py }
- rex_ref: src/dashboard/utils/throttle.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED on each cause separately, including by re-keying the limiter on the session to prove the survives-a-new-session test is not vacuous.

## guard-scope-is-a-hand-written-list
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a check is correct on everything it looks at, and what it looks at is a list somebody typed. It never reports the things it does not cover, so its silence reads as coverage and its scope shrinks every time the codebase grows.
- signature: `python3 -m pytest tests/test_contamination_scope_is_derived.py tests/test_roadmap_index_is_honest.py -q`
- root_cause: two instances, hours apart, both on 2026-08-22. `tools/tenant_contamination_check.py` — step 5 of `make artist-preflight`, whose claim is "no row under this tenant belongs to someone else" — named eight tables out of the seventy the schema carries, with no Spotify entry at all while the schema held some thirty `meta_*` tables. And `test_every_waiting_row_names_the_gesture_it_waits_on` matched roadmap rows against ten hand-written French verbs, so it FAILED R22, a row naming three gestures including a literal shell command, for using none of those ten words.
- long_term_fix: derive the scope and assert the derivation covers everything. The contamination tool groups tables by platform PREFIX read from `information_schema`, and a companion test fails when a tenant-scoped table is neither claimed by a prefix nor listed in `_OUT_OF_SCOPE` with a reason. The roadmap guard asks a structural question instead of a lexical one — every waiting row must have a section in the runbook — which cannot be satisfied by rewording the row.
- autofix: none
- guard: { type: pytest, ref: tests/test_contamination_scope_is_derived.py }
- rex_ref: tools/tenant_contamination_check.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Expanding the scope immediately surfaced `youtube_channel_history` (34 rows), a table the eight-name list had never looked at. Verified RED by removing the Spotify platform, by adding an excuse with no reason, and by naming a table that no longer exists.

## input-nobody-would-type-reaches-the-driver
- status: guarded
- severity: P3
- kind: deterministic
- symptom: a caller-supplied string reaches the database driver in a shape the driver refuses, and the refusal is an unhandled exception rather than a rejected request. The endpoint answers 500 to anyone who asks that way, and no test in the repo produces it — every existing test passes a plausible value.
- signature: `python3 -m pytest tests/test_api_survives_hostile_input.py -q`
- root_cause: `src/api/routers/streams.py::get_timeline` passes `song` into `fetch_df` as a parameter, which is correct — the value IS parameterised, so this is not injection. A NUL byte cannot exist in a Postgres text value at all, so psycopg2 raises `ValueError: A string literal cannot contain NUL (0x00) characters` (`postgres_handler.py:242`) before any SQL is sent, and nothing above it catches a ValueError. Found by fuzzing (`schemathesis`, R22): 596 generated cases, exactly one crashed.
- long_term_fix: the check is at the EDGE, on the raw query string, in `security.reject_nul_bytes_middleware` — so every string parameter the API grows later inherits it without its author remembering, which is what a per-endpoint validator cannot promise. Deliberately not on the body: reading it would break `/webhooks/stripe`, whose signature covers the exact bytes.
- autofix: none
- guard: { type: pytest, ref: tests/test_api_survives_hostile_input.py }
- rex_ref: src/api/security.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Only ONE of the 14 tests goes red when the middleware is removed — the mocked database accepts a NUL happily, so the parametrised "never 500s" cases cannot see the defect. That is recorded in the file itself, next to a DB-gated test proving the real driver does raise; the two ends together are what make the middleware more than decoration. Re-fuzzed across four seeds, 1730 cases, zero 5xx.

## repo-copy-of-a-config-is-not-what-runs
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a config file lives in the repo, looks authoritative, and is not the one the service loads. Editing it changes nothing, reading it describes a deployment that no longer exists, and applying it would undo months of production changes nobody wrote down.
- signature: `grep -q 'caddy-drift' Makefile`
- root_cause: `deploy/Caddyfile` was written in June and never re-read. Production moved to Cloudflare ORIGIN CERTIFICATES, gained an access-log block that deletes `Cookie`/`Authorization`/`Set-Cookie` (2026-06-14), gained `lb_try_duration`, and merged the apex into the dashboard site block — none of it reflected back. `make sync-check` compared the SCHEMA and the git HEAD, and a reverse proxy is neither, so the divergence was invisible to the one command whose job is "is the repo what runs".
- long_term_fix: `make sync-check` now diffs `deploy/Caddyfile` against `/etc/caddy/Caddyfile` on the target and fails on any difference, comparing from the first `{` so the repo copy may carry a comment header explaining how to deploy it. The repo copy was re-synced from the live file rather than the other way round — the running config is the truth, the file was the stale one.
- autofix: none
- guard: { type: make-precondition, ref: Makefile (sync-check, caddy-drift step) }
- rex_ref: deploy/Caddyfile
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Found by trying to patch it: an R22 header fix was written into the repo copy in the belief it was live, and only a `curl` against the real host showed the headers had not changed. Verified RED by appending one comment line to the repo copy.
  - 2026-08-22: a second defect on the way out, worth recording because it is the opposite mistake. The first live fix put the new CSP in the SHARED `(security_headers)` snippet — and Caddy's `header` REPLACES rather than appends, so it overwrote the API's `default-src 'none'` (set by `security_headers_middleware`) with a strictly weaker policy. Caught by re-reading both hosts' headers after the reload. The CSP now sits on the dashboard site block alone.

## resave-erases-a-secret-the-form-cannot-show
- status: guarded
- severity: P1
- kind: deterministic
- symptom: pressing "save" on a form destroys a stored secret the form has no field for. The UI reports success, nothing logs a warning, and the loss only surfaces one collection cycle later as a credential that "stopped working".
- signature: `python3 -m pytest tests/test_saving_a_tab_never_destroys_a_secret.py -q`
- root_cause: `credentials/_core.py::_save_credentials` upserted `token_encrypted = EXCLUDED.token_encrypted` — an overwrite — while `_render.py::_handle_save` computes `encrypted_blob = ''` whenever no SECRET field on the tab holds a value. Two of the four tabs declare no secret field at all (`soundcloud`: only `user_id`; `meta`: only `account_id` + `ig_user_id`), so they could ONLY ever save an empty blob. Both rows nevertheless hold one in production, written by something else: the rotated OAuth refresh_token (`soundcloud_api_collector.py:132`, 228 B) and the System User token (`tools/dev/inject_meta_token.py`, 804 B) that every tenant's Meta AND Instagram collection depends on.
- long_term_fix: `COALESCE(NULLIF(EXCLUDED.token_encrypted, ''), artist_credentials.token_encrypted)` — an empty blob now means "leave it alone". Erasing a secret must be a gesture someone asks for, never a side effect of saving something else. The general shape: a surface that cannot DISPLAY a value must not be able to DELETE it.
- autofix: none
- guard: { type: pytest, ref: tests/test_saving_a_tab_never_destroys_a_secret.py }
- rex_ref: src/dashboard/views/credentials/_core.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Found while auditing why tenant credentials "stopped working" twice. Verified RED on both secret-less tabs by restoring the overwrite. The file also pins WHICH tabs are secret-less, so adding a secret field to one of them forces a re-read of the reasoning instead of silently changing what the tests mean. A mocked test could not have caught this: the defect is in the SQL.

## delivery-failure-logged-as-success
- status: guarded
- severity: P1
- kind: deterministic
- symptom: the code path that sends a notification returns a "did not send" value, the very next line logs that it was sent, and the task ends green. The findings inside the message were computed correctly and rendered correctly; nobody received them.
- signature: `python3 -m pytest tests/test_alert_delivery_is_proven.py -q`
- root_cause: `airflow/dags/alert_monitor.py` ended with `EmailAlert().send_alert(subject, body)` followed by an unconditional `logger.info("Consolidated alert sent")`. `send_alert` returns False — never raises — when `SMTP_USER`/`SMTP_PASSWORD`/`ALERT_EMAIL` are absent from the container. Production logs show three consecutive nights (16, 17, 18 August 2026) writing that success line immediately after the module warned "Email alerts non configurées". The existing guard `test_alert_monitor_sends_what_it_finds.py` covers the hop before this one — that every finding takes part in the send DECISION — and structurally cannot see whether the send SUCCEEDED.
- long_term_fix: `email_alerts.deliver_or_raise()` for the one path whose silence is the incident — it raises, naming which of the two failures occurred (env absent vs send refused), so the task goes red and `on_failure_callback` fires. `send_alert` keeps its non-raising contract for its six other callers. Persistent proof in `monitoring_run` (migration 073) written BEFORE the attempt and updated after, so an external reader on another mail path sees the failure. And an AST sweep that fails on any `send_alert`/`send_email` call whose result is a bare expression — the generalisation, which caught two more sites the day it was written.
- autofix: none
- guard: { type: pytest, ref: tests/test_alert_delivery_is_proven.py }
- rex_ref: airflow/dags/alert_monitor.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Sibling of `finding-rendered-but-not-alerted`: there a finding reached the body but not the decision; here the decision fired and the delivery was never checked. Same root — one boolean carrying two questions. Verified RED by restoring the discarded call.

## static-hint-contradicts-the-live-probe
- status: guarded
- severity: P2
- kind: deterministic
- symptom: two layers answer the same question about a tenant. One reads the database and guesses at the cause from a fixed string; the other calls the platform API and knows. The guess is the one that runs automatically, so the operator and the artist are told something that is not true.
- signature: `python3 -m pytest tests/test_readiness_carries_the_live_diagnosis.py -q`
- root_cause: `artist_readiness` derives status from (declared identity × row recency) and attaches a static `nodata_hint` per platform. `CONNECTION_TESTS` calls the real API and returns the actual reason, but only ran on a human's click or `make artist-preflight`. Measured on GRiNCH (tenant 13) the same night: the probe said "User ID 72854583 joignable, mais aucun titre public n'y est rattaché"; the nightly alert said "vérifie le User ID ; l'app SoundCloud partagée doit être configurée (admin)" — wrong, and blaming the artist and the admin for an account that simply has no public tracks.
- long_term_fix: `src/utils/platform_probes.py` is the headless seam onto the same probes, and `artist_readiness(db, artist_id, probe=…)` takes an optional prober whose answer REPLACES the static hint. Three rules keep the cure from becoming the disease: the probe defaults to None so no existing caller changes behaviour; it runs ONLY where the database already says red (freshness is the proof, the probe is the explainer — 2 API calls a night, not 35); and it never changes a status, only the wording, so a network blip cannot turn a collecting tenant red. `probe_ran` distinguishes "not measured" from "measured and fine".
- autofix: none
- guard: { type: pytest, ref: tests/test_readiness_carries_the_live_diagnosis.py }
- rex_ref: src/utils/platform_probes.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. The load-bearing test is the GRiNCH regression expressed as data — the flag must contain "aucun titre public" and must NOT contain "l'app SoundCloud partagée". Verified RED twice: once by ignoring the probe, once by probing every platform instead of only the reds.

## detector-written-and-never-called
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a function exists whose docstring names an error class, it has unit tests, and nothing in production calls it. The catalogue and the module both read as though the class is covered.
- signature: `python3 -m pytest tests/test_no_detector_is_written_and_never_called.py -q`
- root_cause: `src/utils/monitoring_checks.silent_zero_findings` — "configured tenant × platform with ZERO recent rows, the silent-success class" — was imported only by `tests/test_monitoring_checks.py`. No caller in `src/`, `airflow/` or `tools/`. Worse than a missing guard: a reader auditing coverage found it and moved on.
- long_term_fix: the function was DELETED, not wired, because its predicate is exactly what `artist_readiness.platform_status` already computes as NO_DATA and `readiness_red_flags` already reports nightly — waking it would have produced two voices for one finding (`watchdog-becomes-the-noise`). A note in the module says so, so the decision does not become a cycle. The guard asserts every public function in `monitoring_checks.py` has a caller outside its own module, and separately that this one stays deleted WITH its explanation.
- autofix: none
- guard: { type: pytest, ref: tests/test_no_detector_is_written_and_never_called.py }
- rex_ref: src/utils/monitoring_checks.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Found by asking, of every monitoring helper, "who calls this?" — the same question that found the roadmap guard matching a hand-written verb list. The answer is worth asking of any module whose entire purpose is to be called by something else.

## age-computed-against-another-clock
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a staleness check compares a stored timestamp against a clock that is not the one that wrote it. The verdict is wrong by the offset between the two, in the OPTIMISTIC direction — a genuinely stale source keeps reading fresh — and in the extreme it reports a row in the future.
- signature: `python3 -m pytest tests/test_freshness_uses_one_clock.py -q`
- root_cause: `src/utils/freshness_monitor.py` computed `datetime.now() - val`. `datetime.now()` is NAIVE, so it is the CONTAINER's local time, while psycopg2 converts an aware timestamp to the SESSION timezone when writing into a `timestamp without time zone` column — Europe/Paris in production. Measured 2026-08-22 from a container with no `TZ`: SoundCloud reported an age of **-1h**. It agreed at all only because the Airflow scheduler happens to run in Paris.
- long_term_fix: the age is computed by Postgres in the same statement that reads the value (`EXTRACT(EPOCH FROM (now() - MAX(col)))/3600`). One clock, and it is the clock of the database that holds the rows. The guard asserts both the shape (no argless `now()`/`utcnow()` anywhere in the module) and the behaviour (the reported age does not move when the process timezone changes).
- autofix: none
- guard: { type: pytest, ref: tests/test_freshness_uses_one_clock.py }
- rex_ref: src/utils/freshness_monitor.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Verified RED by restoring the Python subtraction and running under `TZ=Pacific/Kiritimati`. The behavioural half matters more than the structural one: a future `datetime.now(tz)` would pass the AST check and still be a second clock.

## audit-scope-restated-not-derived
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a check iterates a hand-typed list of the things it audits while a registry of those things already exists. The list is a subset, and the difference is invisible — the audit reports cleanly on what it never looked at.
- signature: `python3 -m pytest tests/test_audit_scope_is_derived.py -q`
- root_cause: `alert_monitor.MONITORED_PLATFORMS = ['spotify','youtube','soundcloud','meta']` — four names, while `tenant_identity.PLATFORM_IDENTITIES` has five. **Instagram was never audited.** Compounded by `if not creds`, which tested the credentials dict for EMPTINESS rather than for a declared identity: Benken's `meta` row holds an `account_id` and nothing else, so it counted as "credentials present" for a platform that has never produced a row — and would have counted as proof for Instagram too, since the two share one storage row.
- long_term_fix: the scope is `sorted(PLATFORM_IDENTITIES)`, and presence is judged by `declared_identities()` — the helper written for exactly this question. The guard fails if a literal list returns, if the audited set differs from the registry, or if a `not creds` truthiness test reappears (checked on the AST, because a text search matched the comment explaining why it is wrong).
- autofix: none
- guard: { type: pytest, ref: tests/test_audit_scope_is_derived.py }
- rex_ref: airflow/dags/alert_monitor.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Same family as `guard-scope-is-a-hand-written-list`, one level up: there the scope of a GUARD was typed by hand, here the scope of an AUDIT.

## upsert-freezes-its-own-timestamp
- status: guarded
- severity: P2
- kind: deterministic
- symptom: an upsert refreshes a row's data and leaves its `collected_at` at the value of the first insert. The rows are current; every reader of `MAX(collected_at)` reports the date of the first collection, forever.
- signature: `python3 -m pytest tests/test_upsert_refreshes_its_timestamp.py -q`
- root_cause: `src/collectors/_meta_upsert.py` omitted `collected_at` from `update_columns` on the three config tables and on all but one insight table. Measured 2026-08-22: `pg_stat_user_tables` showed **17 545 UPDATE and 0 INSERT on `meta_insights`** that morning while `MAX(collected_at)` said 29 May. The payloads carried the key all along — it was discarded on conflict.
- long_term_fix: `collected_at` is appended to every insight table's update list by a loop rather than typed 25 times, and added explicitly to the three config literals. The guard checks the SHAPE across every table plus a live round-trip (upsert twice, the clock must move) and its inverse (omit the column, the clock must freeze) so the assertion is not true of any upsert at all.
- autofix: none
- guard: { type: pytest, ref: tests/test_upsert_refreshes_its_timestamp.py }
- rex_ref: src/collectors/_meta_upsert.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Exactly one table already had it — `meta_insights_performance_day`, which is also the only Meta table `freshness_monitor` watches. The monitor was pointed at the one clock that moved, which is why the discrepancy never surfaced as an alert and had to be found by reading `pg_stat_user_tables`.

## two-doors-onto-one-database
- status: guarded
- severity: P2
- kind: deterministic
- symptom: two halves of one application resolve the same database by two different precedences, and neither works in the other's configuration. Moving a variable that looks standard breaks one half in silence.
- signature: `python3 -m pytest tests/test_one_door_onto_the_database.py -q`
- root_cause: `dashboard/utils/get_db_connection` read `DATABASE_URL` → `config.yaml` and never `DATABASE_HOST`; `pg_connect.resolve_kwargs` reads `DATABASE_HOST` → `config.yaml` and never `DATABASE_URL`. Measured in production 2026-08-22: the dashboard and api containers carry ONLY `DATABASE_URL`, the Airflow scheduler carries ONLY `DATABASE_HOST/NAME/USER`, and no container has a `config.yaml`. So each half depended on the one mechanism the other ignored.
- long_term_fix: `get_db_connection` delegates to `PostgresHandler.from_env_or_config()`, which already knew all three sources — it was written on 2026-08-21 for this reason and its docstring already described the asymmetry. The guard is a RATCHET over the 14 pre-existing direct readers: the list may shrink, never grow, and a companion test fails when an entry goes stale.
- autofix: none
- guard: { type: pytest, ref: tests/test_one_door_onto_the_database.py }
- rex_ref: src/dashboard/utils/__init__.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Rewriting fourteen DAGs was not the ask and would have been risk without benefit; the ratchet stops a fifteenth precedence appearing, which is the actual failure mode.

## unmeasured-rendered-as-measured
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a status display shows a green indicator for something nobody has checked. The viewer cannot tell "verified and fine" from "never asked", and acts on the first reading.
- signature: `python3 -m pytest tests/test_status_matrix.py -q`
- root_cause: the setup matrix must not call a platform API while rendering — Streamlit reruns the page on every widget interaction, so probing on render is five API calls per click per tenant. That constraint makes "we have not measured this" a common state, and the tempting shortcut is to render it like a pass.
- long_term_fix: three rules in `src/dashboard/utils/status_matrix.py`, each with a test: arriving data counts as proof without any probe (freshness IS the proof); a platform with no remembered verdict renders `?` in grey, never a tick; and a remembered verdict always carries its age, so a nine-day-old measurement cannot read as today's. The verdicts are persisted by the nightly run (`tenant_platform_probe`, migration 075) so the artist reads the same sentence the alert email carries.
- autofix: none
- guard: { type: pytest, ref: tests/test_status_matrix.py }
- rex_ref: src/dashboard/utils/status_matrix.py
- first_seen: 2026-08-22
- History:
  - 2026-08-22: `guarded`. Same rule as `probe_ran` in the nightly readiness path, applied to a screen instead of an email. Verified RED by making an absent verdict render green, and by probing on render.

## pipeline-writes-to-the-copy-nobody-reads
- status: guarded
- severity: P2
- kind: deterministic
- symptom: an automated capture → validate → publish loop runs, reports success, and produces nothing anyone sees. Each stage is individually correct; the output lands in a duplicate of the target file that stopped being read months earlier. The loop cannot report the problem, because from where it stands it wrote the file it was told to write.
- root_cause: two files carry the same name and the same role. `DEVLOG.md` at the repo root is the living journal — `/resume` step 3 reads it, `pre_compact.py` and `session_summary.py` (4 sites) point at it. `.claude/dev-docs/DEVLOG.md` is a copy frozen at 2026-06-11. `draft_devlog.py:27` (`_DEVLOG_PATH`) tested the frozen copy for "does today already have an entry?", and `/devlog-promote` inserted promoted entries into it. Measured 2026-08-23: two entire sessions (2026-08-21 afternoon→night, 45 commits; and the night of 2026-08-21→22) had no DEVLOG page anywhere, and the 2026-08-21 draft sat in `pending-devlog.md` with its `issue`/`fix` slots unfilled for two days with nothing signalling it.
- signature: `python3 -m pytest tests/test_devlog_is_written_where_it_is_read.py -q`
- long_term_fix: both writers repointed at the live file; the frozen copy now announces itself as an ARCHIVE in its first line. The guard reads the **AST** of every `.claude/hooks/*.py` and `.claude/scripts/*.py` for DEVLOG *path* literals (a text search passes on the explanatory comment that names the wrong path — the lesson of the four hollow guards of 2026-08-22), and excludes prose strings that merely mention `DEVLOG.md`. The slash command has no AST, so it is guarded by its **consequence** instead of its wording: `test_the_archive_stays_behind` fails the moment the archive's newest entry reaches or passes the live file's, which is exactly what a promotion into the wrong file does.
- autofix: none
- guard: { type: pytest, ref: tests/test_devlog_is_written_where_it_is_read.py }
- rex_ref: .claude/commands/devlog-promote.md
- first_seen: 2026-08-23
- History:
  - 2026-08-23: found while soldering a stale `pending-devlog.md`, not while looking for it — the draft pointed at a hook, the hook pointed at a file, and the file's newest entry was ten weeks old. Sibling sweep over every `.claude/` reference to a DEVLOG path: **exactly two** writers targeted the dead copy (`draft_devlog.py`, `/devlog-promote`); all six readers were already correct, which is why the divergence produced silence rather than a contradiction. Sister of `config-corrected-in-the-file-that-loses` — there the *fix* went into the file that loses, here the *output* does. The four assertions were each seen red by mutation (path reverted; ARCHIVE banner removed; `/resume` phrase changed; a fake entry promoted into the archive) and green after.

## decision-made-on-a-string-truncated-for-display
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a branch written to handle a known, valid edge case never executes. The code reads correctly, the condition names the right thing, and reviewers confirm the case is handled — but in production the exception is raised anyway, every time.
- root_cause: control flow was decided by searching a string that had been shortened for DISPLAY. `src/collectors/youtube_collector.py` tested `'playlistNotFound' in safe_error(he)`; `src/utils/safe_error.py::safe_error` truncates at 300 characters for LOG HYGIENE, and in a real googleapiclient repr the URL alone is ~170 characters, putting the token at index **455 of 531**. Measured 2026-08-23: `youtube_daily` retried 3x and raised nightly for tenant 12, whose channel simply has no videos, and the channel snapshot already fetched was lost with the exception. The DAG stayed SUCCESS, the tenant went `stale`, and `readiness_red_flags` excludes `stale` — so nobody was told for two nights.
- signature: `python3 -m pytest tests/test_empty_youtube_channel_is_not_an_error.py -q`
- long_term_fix: decide on the STRUCTURE the API already provides — `HttpError.error_details` is a list of dicts carrying a machine-readable `reason`. The helper moved to `src/utils/api_errors.py`, which imports no vendor SDK, because keeping it beside `from googleapiclient.discovery import build` made its own test uncollectable on any machine without the Google SDK (a guard that silently does not run is the defect this repo keeps rediscovering). The first assertion pins the PROPERTY that killed the old test — `'playlistNotFound' not in safe_error(err)` — so a substring test cannot be reintroduced and start passing by luck if the truncation limit ever changes.
- autofix: none
- guard: { type: pytest, ref: tests/test_empty_youtube_channel_is_not_an_error.py }
- rex_ref: .claude/rules/python.md
- first_seen: 2026-08-23
- History:
  - 2026-08-23: sister of `a guard reads structure, not text` (2026-08-22, four guards that failed on their own comment). Same root, opposite direction: there a guard READ text it should have parsed; here a branch DECIDED on text that had been cut. Both are the consequence of treating a human-facing rendering as a machine-readable value. The mutation that proves it restores the original test verbatim and turns two assertions red.

## per-tenant-outcome-not-recorded
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a multi-tenant job reports SUCCESS while one tenant collected nothing. The per-tenant `try/except/continue` that keeps one bad tenant from aborting the fleet is correct — but its only witness is a WARNING line in a task log, and the task's return value lists the tenants that WORKED, so the failing one is absent rather than named. No surface can then answer "did collection run for this tenant?".
- root_cause: the run ledger existed and was wired to one DAG. Measured 2026-08-23: over its entire history `etl_run_log` held rows for exactly two dag_ids — `meta_ads_api_daily` (195) and `meta_insights_watcher` (13, stopped in May). Spotify, YouTube, SoundCloud and Instagram had **never written a row**, and `src/utils/dag_run_logger.py::DagRunLogger` had exactly one caller. Three dashboard surfaces that read the ledger (`views/etl_logs.py`, `views/alerts.py`, the `has_runs` KPI in `views/home.py`) were blind on four platforms out of five. Concretely: `youtube_daily` was SUCCESS every night while tenant 12 failed inside the loop; freshness eventually turned that tenant `stale`, and `readiness_red_flags` excludes `stale`, so nobody was ever told.
- signature: `python3 -m pytest tests/test_every_collection_dag_records_its_tenants.py -q`
- long_term_fix: a one-call API (`record_tenant_success` / `_failure` / `_skip`) that fits the per-tenant isolation shape without re-indenting the loop or swallowing the exception the loop deliberately catches. `skipped` is not optional: a tenant who declared no identity is in a CORRECT state but must still leave a row — absence of a row is indistinguishable from "the DAG never looked". The guard derives its scope from the AST (a DAG that imports from `src.collectors`) and asserts **branch coverage**: every `continue` inside a per-tenant loop must be preceded by a recorder call.
- autofix: none
- guard: { type: pytest, ref: tests/test_every_collection_dag_records_its_tenants.py }
- rex_ref: src/utils/dag_run_logger.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: the guard was too weak on its first mutation and the mutation is what said so. Checking "is a recorder called in this file" left `instagram_daily` green after deleting one of its two `record_tenant_skip` calls — a ledger with a hole reads exactly like a complete one. Strengthened to per-branch coverage; the same mutation then went red. Two collectors had to start returning a row count (`SoundCloudCollector.run`, `InstagramCollector.run` both returned `None`), because `rows_inserted = 0` would have made "collected nothing" and "did not run" the same value — the very ambiguity the ledger exists to remove. Also fixed on the way: `DagRunLogger.__exit__` wrote `str(exc_val)` into `error_message`, a PERSISTED and dashboard-rendered field — and because the exception arrives as an `__exit__` **parameter** rather than an `except … as e`, it is the one shape the `secret-in-an-exception-message` AST detector is blind to by construction.

## stopped-collecting-is-not-a-status-anyone-reads
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a tenant whose collection worked and then stopped produces no signal anywhere. The credential is valid, rows exist from before, the DAG reports SUCCESS, and every screen is green except the artist's own, which quietly stops moving.
- root_cause: three independent doors, all shut. (a) The per-tenant `try/except/continue` that stops one bad tenant aborting the fleet leaves the task SUCCESS, so `check_dag_failures` sees no FAILED run. (b) `artist_readiness` computes STALE correctly, and `readiness_red_flags` returned only `NO_DATA + BROKEN` — dropping 🟡 on the floor, although "collected, then stopped" is the ONLY shape a working credential can take when it breaks. (c) `alert_monitor.check_data_freshness` did not serialise `error` into its xcom, so a probe that FAILED rendered in the nightly email as "🟡 stale · Airflow UI → relancer le DAG". Measured on Benken (tenant 12) 2026-08-23: two nights, zero signal.
- signature: `python3 -m pytest tests/test_a_tenant_that_stopped_collecting_is_reported.py -q`
- long_term_fix: STALE joins the flags that alert; the freshness xcom carries `error` and `measured_on`, and the email renders a failed probe as "la sonde elle-même a échoué" instead of an action. The STALE `next_action` was rewritten at the same time and that half matters as much: it said "vérifie le DAG youtube" to an ARTIST, who has no Airflow login — the message Cooper condemns in *About Face* p.311 ("demands that he fix a situation that the application can and should usually fix just as well"). Same contract as BROKEN now; the operator gets the DAG name and the literal cause through `etl_run_log` and the nightly mail.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_tenant_that_stopped_collecting_is_reported.py }
- rex_ref: src/utils/artist_readiness.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: the pre-existing `tests/test_artist_readiness.py` asserted `"DAG meta" in next_action(meta, STALE)` — it PINNED the defect. Its premise died rather than the test being deleted, and the reason is written where the assertion was.

## mandatory-filter-with-no-guard
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a rule stated in bold in `CLAUDE.md` is enforced by memory alone. It holds for months, then one query forgets it and the number shown to a user is silently wrong by a factor of ~2.
- root_cause: Spotify for Artists CSVs carry a summary row whose `song` is the artist's own name, so every read of `s4a_song_timeline` must add `AND song NOT ILIKE '%1x7xxxxxxx%'`. The 2026-06-11 audit found two unfiltered queries in `trigger_algo/_tab_budget_roi.py` and the displayed cost per stream had been halved. **The two sites were fixed and no guard was written.** Measured 2026-08-23: the table is named 109 times across `src/` and `airflow/`, the filter appears 30 times, and `data_quality_check.py` queries it five times with the filter zero times.
- signature: `python3 -m pytest tests/test_the_total_row_is_always_filtered_out.py -q`
- long_term_fix: an AST walk over every SQL literal, flagging only reads that can DOUBLE A TOTAL. Four exemptions, each measured rather than assumed: the parameterised form `song NOT ILIKE %s` (the repo's preferred style), a read pinned to one song (`song =` / `TRIM(song) =`), an existence probe (`COUNT(*) … LIMIT 1`), and a shell command rendered on a help page. The detector is pinned against synthetic modules so it cannot rot into a no-op.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_total_row_is_always_filtered_out.py }
- rex_ref: .claude/rules/python.md
- first_seen: 2026-08-23
- History:
  - 2026-08-23: **the guard's first version reported 23 files, nearly all correct** — it looked for the literal `1x7xxxxxxx` and the repository mostly passes the filter as a PARAMETER. That is `watchdog-becomes-the-noise`, caught before shipping by reading the flagged sites instead of trusting the count. Each refinement moved the predicate closer to the QUESTION ("can this read double a total?") and away from the table name: 23 → 10 → 5 → **2**, and the final 2 were both real.

## detector-with-no-scheduler
- status: guarded
- severity: P2
- kind: deterministic
- symptom: a detector is written, tested, documented — and nothing ever runs it. It reports on the day a human happens to type its command, which is never the day the defect appears.
- root_cause: `tools/tenant_contamination_check.py::scan()` was reachable only from `make tenant-check` and from step 5 of `artist_preflight`, and `alert_monitor.check_canary_preflight` runs steps 2-4 only. So the ONE class this repository has actually been bitten by — every tenant's Spotify popularity history filed under `artist_id = 1` for months in production — was the one class with no watchdog. The other checks cannot see it by construction: rows ARE arriving, so freshness, readiness and the canary are all green; they just belong to somebody else.
- signature: `python3 -m pytest tests/test_every_nightly_check_is_scheduled_and_heard.py -q`
- long_term_fix: the scan runs nightly inside `alert_monitor`, importing `tools.` as a namespace package after `sys.path.insert(0, '/opt/airflow')` — with the ImportError branch that pushes "check could not run" as a FINDING, never a pass. The guard asserts the three separate links of the chain, because breaking any one of them produces the same silence: a `check_*` function has an operator, the operator is upstream of the sender, and the finding is named in `has_issues` (that third link is the 2026-08-21 defect, where `central_apps_broken` was in the body and the subject but not in the send decision).
- autofix: none
- guard: { type: pytest, ref: tests/test_every_nightly_check_is_scheduled_and_heard.py }
- rex_ref: airflow/dags/alert_monitor.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: found by asking, of each detector in the repo, "who runs this?" — the same question that found `run_freshness_alerts` had zero callers. A detector's existence is not its execution.

## script-replaced-while-it-runs
- status: reported
- severity: P2
- kind: manual
- symptom: a deploy script is updated, pushed, and the very deploy that pulls the update does not run it. The run reports success, so the change looks deployed — and it is, on disk, for NEXT time. Nothing says the new step was skipped.
- root_cause: `tools/deploy.sh` begins with `git pull --ff-only origin main` and therefore rewrites ITSELF mid-execution. bash reads a script incrementally rather than into memory, so the running process keeps executing the bytes it already read while the file underneath has been replaced. Measured 2026-08-23: the env-parity gate was added in the same commit that was being deployed, `deploy.sh` on the box contained it afterwards (`grep -c` = 1), and the gate produced no output during that run. The deployment succeeded and the new guard silently did not fire.
- signature: `grep -qE 'DEPLOY_REEXECED' tools/deploy.sh`
  <!-- NO leading `!`: here the pattern searched for is the FIX, not the defect.
       The catalogue contract is "exit non-zero when the ANTI-PATTERN is present",
       and the anti-pattern is the re-exec being ABSENT — so a bare grep is right.
       The first version carried the `!` by habit and exited 1 on the CORRECTED
       code, i.e. it would have reported the fix as the defect. Verified both ways
       by mutation: 0 on the fixed script, 1 once the re-exec is removed. -->
- long_term_fix: re-exec after the pull when HEAD moved — `DEPLOY_REEXECED=1 exec bash "$0" "$@"`, guarded by the variable so it cannot loop. The general shape: a script that updates its own source must restart from the new source, or it is running one version while claiming to have deployed another. `kind: manual` because the only conclusive proof is a real deploy that changes the script — a signature can check the re-exec is present, not that it works.
- autofix: none
- guard: { type: signature, ref: tools/deploy.sh }
- rex_ref: tools/deploy.sh
- first_seen: 2026-08-23
- History:
  - 2026-08-23: found by reading the deploy output instead of trusting its "✅ deployed" line — the gate's absence was visible only to someone who knew it should have printed. Sister of `collector-shipped-dag-not-rerun` and of the api/dashboard images that COPY `src/` at BUILD time: in all three, the artifact was updated and the thing actually running was not.

## test-leaves-a-hole-in-sys-modules
- status: guarded
- severity: P2
- kind: deterministic
- symptom: tests are green file by file and red in a full run, on assertions unrelated to whatever changed. The failing test's own monkeypatch appears not to take effect — the real implementation runs instead of the fake one — and the failure moves between runs as the order changes.
- root_cause: a test replaced `sys.modules["…"]` with a stub and, in its `finally`, called `del` instead of restoring the previous value. Deleting the key EVICTS the real module for the rest of the session: the next import re-executes it from disk and hands out a SECOND module object, while every module that already did `from … import NAME` still holds the first. A later `monkeypatch.setattr("pkg.mod.NAME", …)` then patches one object while the code under test reads the other. Measured 2026-08-23 in `tests/test_readiness_carries_the_live_diagnosis.py:192` on `src.dashboard.views.credentials._registry`; CI failed on `test_a_raising_probe_becomes_a_red_not_a_traceback`, whose output showed the five REAL probes running despite a monkeypatch to a single fake one.
- signature: `python3 -m pytest tests/test_no_test_deletes_a_module.py -q`
- long_term_fix: borrow, never evict — `previous = sys.modules.get(key)` before, and restore it (or `pop` only when there was nothing) after. The guard walks the AST of every test for `del sys.modules[…]` and for `sys.modules.pop` without a saved previous value, because the trap is invisible in a single-file run: the test that causes it always passes.
- autofix: none
- guard: { type: pytest, ref: tests/test_no_test_deletes_a_module.py }
- rex_ref: tests/test_readiness_carries_the_live_diagnosis.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: three reproductions failed before this was found, and each failure was informative — the test passes alone, passes with its neighbour, and passes with the environment stripped. What it does NOT survive is a full run, which is the only condition CI uses. The lesson is about method: an order-dependent failure cannot be reproduced by narrowing, only by running the whole thing.

## tool-imports-the-app-without-a-path
- status: guarded
- severity: P1
- kind: deterministic
- symptom: a standalone script under `tools/` dies at startup with `ModuleNotFoundError: No module named 'src'`, however it is invoked — including from the repo root. Downstream, the crash is read as the script's own verdict: `audit_runner` saw `check_manifest_consistency.py` exit 1 and reported a `streamlit-pin-drift` hit that did not exist, and the 04h production drift cron `notify_schema_drift.py` was silenced by the very import meant to harden it.
- root_cause: Python seeds `sys.path` with the SCRIPT's own directory, never the caller's cwd, so a file under `tools/` (or `tools/dev/`) cannot import the app package unless it puts the repo root on the path itself. Measured 2026-08-23: widening the credential-redaction guard to `tools/` added `from src.utils.safe_error import safe_error` to six scripts; five already had the path line and two did not. The defect was the SCOPE of the widening — the newly covered files had a different runtime contract than the files the guard was written against — for the fourth time in three days.
- signature: `python3 -m pytest tests/test_a_tool_script_can_actually_start.py -q`
- long_term_fix: the guard walks the AST of every file under `tools/` and requires a `sys.path` mutation strictly BEFORE the first `import src…`; a script with no app import is skipped, so the rule costs nothing to the tools that stay standalone. For a script that is itself the last link of an alert, the app import is additionally wrapped in `try/except ImportError` with a fallback that cannot leak (type name only, no message) — a broken import path must never be able to silence the alert it was added to protect.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_tool_script_can_actually_start.py }
- rex_ref: tools/notify_schema_drift.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: found by running `audit_runner --deterministic` and disbelieving its verdict. It named `streamlit-pin-drift`, a P1 about manifest pins; the actual state was a checker that could not start. A signature that shells out inherits the exit code of a crash and reports it as its own class — so a hit on a class whose symptom does not match the repo is a reason to run the signature by hand, not to fix the class it names.

## test-sends-real-mail-to-real-people
- status: guarded
- severity: P1
- kind: deterministic
- symptom: real email arrives in a real inbox after a test run, from the project's own SMTP account, carrying a `http://localhost:8501` link that no recipient can use. The suite reports all-green: nothing failed, because nothing was asserting about the send.
- root_cause: `tests/conftest.py` had no network boundary of any kind, so a test that presses a UI button reaches the real relay with the credentials in `.env` and a recipient read from whatever database the run points at — locally, the migrated copy of production. Measured 2026-08-23: `test_admin_hypeddit_buttons.py::test_every_button_survives_a_click[admin]` presses every button on the admin view, one of which is `📧 Renvoyer vérification` (`admin.py:685` → `send_verification_email(sel_user['email'], …)`). Three suite runs that day delivered three verification emails to `timothe.baudry137@gmail.com`; had the selected row been a beta tester, it would have been theirs. The `localhost` link is the same default that `env-not-wired-to-service` covers — no local process sets `APP_BASE_URL` — but here the defect is that the mail left at all.
- signature: `python3 -m pytest tests/test_the_suite_cannot_send_mail.py -q`
- long_term_fix: an autouse fixture in `conftest.py` replaces `smtplib.SMTP`/`SMTP_SSL` for every test; a test that means to exercise the send path patches them itself and is never seen by the boundary. It RECORDS the attempt and asserts at teardown rather than only raising, because `send_verification_email` wraps its send in `except Exception` — an exception alone is swallowed and the offending test stays green. The signature trips the boundary on purpose and needs no database, so it is deterministic in CI.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_suite_cannot_send_mail.py + tests/conftest.py::_no_real_smtp }
- rex_ref: tests/test_admin_hypeddit_buttons.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: found from the operator's INBOX, not from any check the repo runs — three emails timestamped within the session's own test runs. No detector could have seen it: every guard in the repo asks whether the code is right, and none asks what the suite does to the outside world. The generalisation worth keeping is that a test suite has a blast radius, and it was never bounded here — SMTP is now, real HTTP is not yet.

## unattributable-payment-link
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un client paie et n'est jamais provisionné. Le paiement réussit côté Stripe, le webhook renvoie 200, et le compte reste sur son ancien plan. Rien n'échoue nulle part : ni la vue, ni le webhook, ni un test.
- root_cause: les deux surfaces de paiement construisaient l'URL du Payment Link en `f"{checkout_url}?client_reference_id={_aid}" if _aid else checkout_url`, donc une session ayant perdu son identifiant de locataire rendait quand même un bouton **payable**, sans le paramètre qui nomme le bénéficiaire. En face, `stripe_webhook.py:140` exécute `if artist_id and customer_id:` — sans `client_reference_id`, il ne fait RIEN et sort en 200. Mesuré 2026-08-23 (R40) sur `views/upgrade.py:125` et `views/billing.py:244`, trouvés ensemble par balayage de la classe.
- signature: `python3 -m pytest tests/test_a_tenant_scoped_action_names_its_tenant.py -q`
- long_term_fix: un lien de paiement non attribuable est pire qu'aucun lien — on ne le rend pas. Bouton désactivé plus un message qui nomme le geste (« reconnecte-toi »). Le garde lit l'AST de chaque `st.link_button` et exige que **toutes** les branches de l'URL portent `client_reference_id`, en résolvant les `Name` à travers les affectations locales.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_tenant_scoped_action_names_its_tenant.py::test_no_payment_link_can_render_without_its_tenant }
- rex_ref: src/api/routers/stripe_webhook.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: le garde a d'abord été écrit VERT sur son propre défaut, et seule la mutation l'a montré. Le code fautif passait la **variable** `_url` à `st.link_button`, assignée une ligne plus haut ; en ne regardant que le site d'appel, le garde voyait un `Name` nu, concluait « ce n'est pas un lien de paiement » et passait. Cinquième fois que la portée du prédicat est le défaut, et la seule chose qui l'ait dit est d'avoir retiré le fix pour regarder la couleur.

## partial-collection-invisible
- status: guarded
- severity: P2
- kind: deterministic
- symptom: la collecte d'un locataire s'effondre sans que rien ne le dise. Des données arrivent — donc la fraîcheur est verte — mais bien moins que d'habitude : 3 titres là où 40 atterrissent. Le DAG est vert, l'e-mail nocturne est muet, et c'est un humain qui finit par le remarquer.
- root_cause: le pilier **Volume** (Moses/Gavish/Vorwerck, *Data Quality Fundamentals* p.144 — « Has all the data arrived? ») n'était surveillé que dans un sens. `check_row_anomalies` ne détecte que le PIC et son docstring délègue explicitement l'autre sens à la fraîcheur : « freshness already covers the opposite (no recent data) ». Vrai de ZÉRO ligne, faux de TROP PEU. Entre les deux il y a un trou, et streaMLytics y est tombé deux fois — SoundCloud « ✅ sur 0 titre » au test GRiNCH, chaîne YouTube vide chez Benken.
- signature: `python3 -m pytest tests/test_a_partial_collection_is_seen.py -q`
- long_term_fix: `check_row_dips` compare, **par locataire**, le dernier jour COMPLET à la moyenne des 7 précédents. Par locataire, parce qu'un total de flotte cache exactement le cas qui compte ; sur le dernier jour complet, parce que comparer une journée en cours à des journées entières ferait rougir chaque matin — un détecteur qui crie tous les jours n'est plus lu. Le seuil vit dans `src/utils/volume_monitor.py`, pas dans le DAG : aucun DAG de ce dépôt n'est importable hors conteneur (l'Airflow installé refuse `schedule_interval`), donc un test qui passe par l'import **skippe en silence** et ne prouve rien.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_partial_collection_is_seen.py }
- rex_ref: src/utils/volume_monitor.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: le premier plancher écrit valait 30 lignes/jour. Mesuré ensuite sur la vraie prod, les volumes par locataire sont 1498/j (canari), 19/j (admin) et **7/j (Benken)** — ce plancher aurait rendu le détecteur aveugle à deux locataires sur trois, dont précisément celui qui a une panne de collecte vivante. Un seuil rond n'est pas une calibration, et c'est le fait d'avoir lu les volumes réels AVANT de figer qui l'a montré. Un test pinne désormais la calibration à ces chiffres, pas à un nombre rond.

## test-calls-a-real-api
- status: guarded
- severity: P2
- kind: deterministic
- symptom: la suite consomme du quota d'API réel et échoue en CI dès qu'il n'y a pas de réseau, sans qu'aucun test ne le dise. Contrairement à son jumeau `test-sends-real-mail-to-real-people`, ce défaut ne laisse **aucune trace** côté opérateur : pas de mail dans une boîte, juste des appels sortants silencieux avec les credentials de `.env`, susceptibles d'écrire sur un vrai compte.
- root_cause: `tests/conftest.py` ne portait aucune frontière réseau. Mesuré 2026-08-23 avec un mouchard sur `socket.connect` pendant une exécution complète : `test_artist_preflight.py::test_a_scoped_run_still_requires_its_own_platform` ouvrait quatre connexions réelles (Meta 157.240.196.17, Google 35.186.224.24, SoundCloud 3.164.85.105) parce que `step_central_apps` sonde les QUATRE plateformes, hors périmètre comprises. Khorikov (*Unit Testing Principles* p.213/221) nomme la ligne : les dépendances *unmanaged* font partie du comportement observable et se mockent ; les *managed* (la base) non.
- signature: `python3 -m pytest tests/test_the_suite_cannot_call_an_api.py -q`
- long_term_fix: fixture autouse posée sur la SOCKET, pas sur `requests` — les collecteurs sortent par `requests`, `googleapiclient` ou `urllib` selon la plateforme, et n'en patcher qu'un aurait laissé les deux autres passer. Seuls les ports 80/443 sont refusés : Postgres (5433) est une dépendance *managed* et doit continuer de passer, sinon ~160 tests d'isolation locataire redeviennent des skips silencieux. Comme pour SMTP, la tentative est ENREGISTRÉE et asservie au teardown, hors de portée du `except` des collecteurs.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_suite_cannot_call_an_api.py + tests/conftest.py::_no_real_http }
- rex_ref: tests/test_artist_preflight.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: trouvé en cherchant, pas en subissant — le défaut SMTP de la veille avait été trouvé par la boîte mail, et la question « qu'est-ce que la suite fait D'AUTRE au monde extérieur ? » a été posée volontairement. La réponse tenait en un mouchard de vingt lignes sur `socket.connect`. Un rayon de souffle se mesure, il ne se déduit pas.

## sender-identity-composed-twice
- status: guarded
- severity: P3
- kind: deterministic
- symptom: les e-mails du produit arrivent sous un nom d'expéditeur qui n'est pas le sien — ici « Music Cross Platform Dashboard & Trigger Spotify » au lieu de « streaMLytics ». Rien n'échoue : les mails partent, sont délivrés, et personne dans le code ne peut dire d'où vient ce nom.
- root_cause: deux chemins d'envoi composaient leur propre en-tête `From`. `verification_email.py` faisait `f"{from_name} <{from_email}>"` — correct ; `email_alerts.py` posait **`self.smtp_user`**, l'identifiant de connexion au relais, sans nom d'affichage et sur le mauvais domaine (`ae8df8001@smtp-brevo.com` en prod, quand `SMTP_FROM` vaut `noreply@streamlytics.fr`). Brevo, qui exige un expéditeur validé, y substitue l'expéditeur par défaut du compte. Et la valeur affichée par l'autre chemin venait de la clé `smtp.from_name` de `config/config.yaml` — le repli que le code lit AVANT son défaut.
- signature: `python3 -m pytest tests/test_every_mail_says_who_it_is_from.py -q`
- long_term_fix: une seule fonction compose l'en-tête (`src/utils/email_identity.from_header()`), et un garde AST interdit tout `msg['From'] = …` qui ne soit pas son appel. L'adresse d'expédition est explicitement distincte du login SMTP : chez un relais, le login est un compte technique, et retomber dessus est un pis-aller, pas le cas nominal.
- autofix: none
- guard: { type: pytest, ref: tests/test_every_mail_says_who_it_is_from.py }
- rex_ref: src/utils/email_identity.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: le coût réel n'est pas le défaut, c'est le diagnostic. La roadmap portait depuis des semaines « le code met déjà `streaMLytics` par défaut et `SMTP_FROM_NAME` est absent des deux conteneurs — le nom vient donc du compte Brevo, **aucune ligne de Python ne peut le corriger** ». Les deux moitiés étaient fausses, et pour la même raison : on avait lu le chemin d'envoi qui marchait, et jamais ouvert `config.yaml`, dont la clé `from_name` portait littéralement le nom observé. Une tâche classée « hors de portée du code » mérite qu'on vérifie la portée avant de la parquer — deuxième fois en trois jours.

## traceback-rendered-to-the-visitor
- status: guarded
- severity: P2
- kind: deterministic
- symptom: une exception non rattrapée affiche sa **traceback complète dans le navigateur** du visiteur — chemins de fichiers, lignes de code, et le message de l'exception. Aucun log ne le signale : de la machine, tout va bien.
- root_cause: `client.showErrorDetails` n'était pas configuré dans `.streamlit/config.toml`, et le défaut de Streamlit est `full`. Ne pas régler l'option n'est pas neutre. Mesuré en production le 2026-08-23 (`streamlit 1.58.0`, valeur effective `full`). Ce dépôt sait ce que ce message peut contenir : Meta et YouTube passent leur credential en QUERY STRING, ce qui est toute la raison d'être de `secret-in-an-exception-message` et de `safe_error()`. Le travail fait pour empêcher un credential d'atteindre un LOG était donc contourné par la surface la plus exposée de toutes.
- signature: `python3 -m pytest tests/test_a_traceback_never_reaches_the_visitor.py -q`
- long_term_fix: `showErrorDetails = "none"` dans la config embarquée ; le visiteur voit un message générique, la traceback reste côté serveur où `public_error_ref()` lui donne déjà une référence à citer. Le débogage local se fait par `STREAMLIT_CLIENT_SHOW_ERROR_DETAILS=full`. Le garde refuse aussi l'ABSENCE de réglage, pas seulement `full` — c'est l'absence qui était le défaut.
- autofix: safe
- guard: { type: pytest, ref: tests/test_a_traceback_never_reaches_the_visitor.py }
- rex_ref: .streamlit/config.toml
- first_seen: 2026-08-23
- History:
  - 2026-08-23: trouvé en répondant à une liste de contrôle sécurité, à la question « erreurs détaillées coupées ? ». Dix-sept des dix-huit points étaient tenus ; celui-là ne l'était pas, et il ne se voyait nulle part — ni dans le code, ni dans un log, ni dans un test. `register.py` avait pourtant déjà reçu `public_error_ref()` pour cette raison exacte (R23) : la décision avait été prise pour UNE page au lieu de l'application.

## boundary-narrower-than-the-surface
- status: guarded
- severity: P2
- kind: deterministic
- symptom: une frontière d'exception EXISTE, elle est documentée, elle fonctionne — et le défaut passe quand même, parce qu'elle n'entoure qu'une partie du code. Le symptôme est indiscernable d'une absence de frontière, sauf sur les chemins couverts.
- root_cause: `app.py` portait un « central view guard » autour de `_render_page` seulement, soit **10 des 90 lignes** de `main()`. Les 80 restantes portaient huit appels de vue, dont les surfaces **non authentifiées** : page vie privée, onboarding, barres latérales. Mesuré end-to-end dans un navigateur le 2026-08-23 avec `showErrorDetails=full` (la valeur EFFECTIVE en production ce jour-là, faute d'avoir été réglée) : une exception sur ces chemins rendait dans la page la clé API YouTube en clair — elle voyage dans la query string, donc dans le message de l'exception — plus les chemins de fichiers et le code.
- signature: `python3 -m pytest tests/test_the_error_boundary_covers_everything.py -q`
- long_term_fix: `main()` n'est plus QUE la frontière : docstring, imports, un `try` autour de `_main_body()`. Le garde lit l'AST et refuse toute instruction de `main()` hors du `try`, ainsi que tout appel `show*` hors frontière ; un troisième test exige le `raise` nu qui laisse passer `st.stop()` / `st.rerun()`, sans quoi la navigation casserait. Le réglage `showErrorDetails=none` devient la SECONDE ligne : un réglage unique dont l'absence est le défaut ne peut pas être la seule.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_error_boundary_covers_everything.py }
- rex_ref: src/dashboard/app.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: trouvé en testant le rendu d'erreur DANS UN NAVIGATEUR, pas en lisant le code — et la lecture du code aurait rassuré, puisque le docstring du dispatch annonce « Wrapped by main()'s error handler ». L'annonce était vraie et la portée fausse. C'est la sixième fois dans ce dépôt que la portée d'un garde est le défaut plutôt que sa logique, et la première où le garde en question n'était pas un test mais du code de production.

## two-surfaces-two-truths
- status: guarded
- severity: P2
- kind: deterministic
- symptom: deux surfaces du produit répondent différemment à la MÊME question, et l'utilisateur croit celle qui a tort. Ici : le PDF exporté annonçait « Spotify ✅ configuré » pendant que la matrice à l'écran disait « ⚪ À connecter », pour le même artiste au même instant.
- root_cause: `_collect_credentials_status` (`src/dashboard/utils/pdf_exporter/_collectors.py`) recalculait son propre verdict au lieu de lire celui de l'écran — `(key in have) or app_level_configured(key)`. Deux faux verts indépendants : `key in have` teste l'existence d'une LIGNE dans `artist_credentials` (un onglet ouvert puis enregistré vide la crée, ce que `declared_identities` existe pour empêcher), et `app_level_configured` rend la plateforme verte **à partir du `.env` de l'administrateur**, pour un locataire qui n'a rien déclaré. Son docstring promettait pourtant de refléter « the green status shown in the app ». Remonté par un artiste en test le 2026-08-23 (« Configuré api alors qu'on avait fait que youtube »).
- signature: `python3 -m pytest tests/test_the_pdf_says_what_the_screen_says.py -q`
- long_term_fix: le PDF LIT `artist_readiness`, la source de l'écran, au lieu de recalculer. Le garde est structurel — il interdit à la fonction d'appeler `app_level_configured` et de requêter `artist_credentials` — parce qu'un test de valeur exigerait une base et skipperait en CI. Une quatrième assertion épingle le prédicat de l'écran (`status != "todo"`) pour que le garde tombe plutôt que de mentir si l'écran change.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_pdf_says_what_the_screen_says.py }
- rex_ref: src/dashboard/utils/pdf_exporter/_collectors.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: le contraste est ce qui rend la classe intéressante — la matrice à L'ÉCRAN était CORRECTE, et l'enquête est partie de l'hypothèse inverse. C'est la surface **imprimée**, celle qui survit à la session et que l'artiste garde, qui mentait. Chercher un faux vert là où on le voit peut envoyer sur la mauvaise surface.

## success-message-outside-its-condition
- status: guarded
- severity: P2
- kind: deterministic
- symptom: l'utilisateur voit défiler des erreurs, puis un message de succès. Il retient le dernier. Ici : sept déclenchements de collecte en échec affichaient sept ❌ **puis** « Lancé ! », et l'artiste repartait attendre des données qui ne viendraient jamais.
- root_cause: dans `show_data_collection_panel` (`src/dashboard/app.py`), chaque déclenchement était correctement testé (`if result.get('success')`), mais le `st.sidebar.success("Lancé !")` final vivait **après la boucle, hors de toute condition de résultat**. Le soin mis sur chaque itération masquait l'absence de conclusion. Même famille que la croix verte de collecte qui atteste un état SUCCESS d'Airflow plutôt que l'arrivée de lignes.
- signature: `python3 -m pytest tests/test_a_success_message_tests_success.py -q`
- long_term_fix: « Lancé ! » n'apparaît que si `launched` est non vide, et une branche d'échec explicite le dit sinon — conditionner le succès sans ajouter l'échec remplacerait un faux vert par un silence, ce qu'une assertion dédiée interdit. Le garde exige que l'appel soit sous un `if` **dont le test porte sur le résultat**, et non sous n'importe quel `if`.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_success_message_tests_success.py }
- rex_ref: src/dashboard/app.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: la première version du prédicat demandait « cette ligne est-elle dans le corps d'un `if` ? » et était **VERTE sur le défaut** — le message fautif vivait déjà sous le `if` du bouton. Être sous une condition ne suffit pas : il faut être sous **la condition qui teste ce qu'on annonce**. Seule la mutation l'a dit ; c'est la septième fois dans ce dépôt que le prédicat d'un garde vise le symptôme au lieu de la question.

## the-page-that-tells-you-what-to-do-is-unreachable
- status: guarded
- severity: P2
- kind: deterministic
- symptom: l'utilisateur ne sait pas quoi faire, et la page qui le lui dirait existe — mais aucun chemin de l'application n'y mène. Rien ne casse, rien ne lève : une page injoignable est silencieuse.
- root_cause: `views/onboarding.py`, seule surface portant la sélection par plateforme et la matrice, n'était dans **aucune section de `_NAV_SECTIONS`** et n'était pas une clé de page valide. Il n'était joignable que par le lien profond `?page=onboarding`, produit à deux endroits : l'écran post-inscription et l'e-mail de vérification. **Mail fermé, onglet fermé : la page n'existait plus.** Et sur l'accueil, les quatre étapes de mise en route nommaient leur destination sans y mener — `for done, label, _page in steps:`, la clé liée puis jetée, rendue en `st.markdown`. Enfin l'atterrissage était inconditionnel sur `home`, qui pour un artiste neuf est un tableau d'état vide.
- signature: `python3 -m pytest tests/test_the_setup_guide_is_reachable.py -q`
- long_term_fix: entrée de navigation permanente, routage, `ALWAYS_ACCESSIBLE` (faire payer le droit de brancher ses comptes n'a pas de sens), aiguillage de première connexion qui rend `onboarding` tant que rien n'est déclaré et `home` ensuite, et étapes d'accueil devenues des boutons. La règle de navigation vit dans `utils/navigation.py` — `onboarding.py` portait déjà sa copie, et une deuxième aurait divergé.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_setup_guide_is_reachable.py }
- rex_ref: src/dashboard/utils/navigation.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: aucune alerte n'était possible — le produit fonctionnait, la page rendait bien quand on l'atteignait, et les tests de rendu passaient puisqu'ils appellent `show()` directement. C'est l'accessibilité, pas le rendu, qui manquait. Un test de rendu ne dit jamais si une page est atteignable.

## dead-content-that-still-ships
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un utilisateur suit une consigne que le produit ne demande plus, et échoue. La consigne vient d'un contenu maintenu, traduit, et que plus rien n'affiche — sauf sur une surface qu'on avait oubliée.
- root_cause: deux corpus de guides d'identifiants coexistaient. Les quatre `_guide_*` des modules plateforme et leur dispatcher `_render_platform_guide` n'avaient **aucun appelant** depuis le passage au modèle central (ADR-006) — 180 lignes et 36 traductions. Ils **contredisaient** le corpus vivant : sur Spotify le vivant dit « tu n'as rien à créer, colle le lien de ta page artiste », le mort disait « crée une app, coche Web API, saisis une Redirect URI ». Et le guide **anglais**, lui, n'était pas mort : miroir périmé du même modèle, il est **expédié dans le PDF d'onboarding** pour `lang == "en"`, avec `http://127.0.0.1:8888/callback` — un `8888` hérité du défaut de `spotipy`, décliné en trois orthographes dans le dépôt, dont la forme `localhost` que le tableau de bord Spotify **refuse désormais**.
- signature: `python3 -m pytest tests/test_a_guide_never_asks_for_a_dead_uri.py -q`
- long_term_fix: le corpus mort est supprimé (code, dispatcher, traductions — `test_i18n_orphans.py` a listé les 36 clés), le guide anglais est aligné sur le modèle central, et un garde interdit qu'un guide artiste demande une Redirect URI ou la case Web API : sous le modèle central l'artiste ne crée aucune app, ces étapes n'existent pas pour lui.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_guide_never_asks_for_a_dead_uri.py }
- rex_ref: src/dashboard/content/credential_guides_en.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: le coût n'est pas le code mort, c'est qu'il RESSORT. Ici par deux chemins : le PDF anglais qui l'expédiait vraiment, et la tête de quiconque ouvre le fichier pour comprendre le flux. Du texte qu'on maintient et qu'on traduit se lit comme du texte qui compte.

## the-feature-is-wired-to-the-function-nobody-calls
- status: guarded
- severity: P3
- kind: deterministic
- symptom: une fonctionnalité est écrite, traduite, complète — et ne s'affiche nulle part. Aucun test ne tombe : la fonction qui la rend existe et fonctionne, elle n'a simplement pas d'appelant.
- root_cause: `utils/os_hints.os_selector()` (bascule Mac/Windows des notices) n'était appelé que depuis `render_credential_guides()`, **sans appelant**. Le chemin réellement emprunté par les onglets, `render_credential_guide_for()`, se contentait de résoudre les jetons par **reniflage du User-Agent avec WINDOWS par défaut**, sans laisser corriger. Un artiste Mac lisait des raccourcis Windows (GRiNCH, 12/08).
- signature: `python3 -m pytest tests/test_the_os_switch_is_visible.py -q`
- long_term_fix: appeler `os_selector()` depuis le rendu vivant, une clé par plateforme (les onglets coexistent dans la même session). Le garde ne teste pas que la fonction existe — il teste qu'elle est appelée **depuis la fonction que les onglets utilisent**, et une assertion séparée épingle quelle fonction c'est, pour tomber plutôt que mentir si le chemin change.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_os_switch_is_visible.py }
- rex_ref: src/dashboard/content/credential_guides_st.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: trois défauts de la même journée ont cette forme — guides morts, sélecteur d'OS, page d'onboarding injoignable. Le dépôt sait détecter du code qui casse ; il ne savait pas détecter du code CORRECT que rien n'atteint. C'est la même famille que `detector-written-and-never-called`, côté interface.

## the-feature-exists-and-the-path-never-reaches-it
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un utilisateur ne peut pas faire une chose que le produit sait faire. La fonctionnalité est écrite, testée, documentée — et le chemin qui y mène s'arrête avant. Rien n'échoue : le journal dit « sauté », avec une raison exacte.
- root_cause: `soundcloud_daily.py` sautait le locataire dès que `user_id` était vide, **avant** d'avoir lu ses titres déclarés, et le constructeur du collecteur levait sur le même critère. Or pour un artiste signé sur un label, le profil personnel n'existe pas et n'existera jamais : l'unité collectable est le TITRE, et `GET /tracks/{id}` rend ses écoutes quel que soit le compte hôte. La fonctionnalité « Mes titres hébergés sur d'autres comptes » existait pourtant en entier — widget, résolution d'URL, `track_platform_link`, `migrations/074`, `fetch_claimed_tracks`. Mesuré sur le cas GRiNCH, 2026-08-23.
- signature: `python3 -m pytest tests/test_a_label_signed_artist_is_collectable.py -q`
- long_term_fix: `has_claimed_tracks()` dans `claimed_tracks.py`, appelée par les DEUX verrous — le DAG avant de sauter, le collecteur avant de lever. Une seule lecture pour deux appelants ; l'écrire deux fois l'aurait laissée diverger. La raison journalisée nomme désormais les deux conditions manquantes, pas une seule.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_label_signed_artist_is_collectable.py }
- rex_ref: src/utils/claimed_tracks.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: le premier jet du correctif recopiait la résolution DSN pour ouvrir sa connexion, et `test_one_door_onto_the_database` l'a refusé sur-le-champ — une quatrième porte sur la base. Un garde posé pour un autre défaut a rattrapé celui-ci le jour même.

## detect-then-reject-with-the-wrong-advice
- status: guarded
- severity: P3
- kind: deterministic
- symptom: un fichier est accepté par la détection puis refusé plus bas, avec un conseil qui ne corrige rien. L'utilisateur applique le conseil, réessaie, échoue à l'identique.
- root_cause: l'export « Depuis le début » de S4A (`…-songs-all.csv`) était détecté par son propre nom de fichier, puis rejeté trois couches plus bas par `_detect_window` avec un message conseillant de **renommer le fichier**. Renommer ne corrige rien : Spotify renvoie auditeurs et sauvegardes à ZÉRO sur cet export — c'est la donnée qui est inutilisable, pas son nom. Deuxième cause du même symptôme : le séparateur `;`, celui que produit Excel en configuration française, n'était pas testé — la ligne d'en-tête se lisait comme une colonne géante et le message disait « type non reconnu » sans nommer le séparateur.
- signature: `python3 -m pytest tests/test_a_refused_csv_says_the_real_reason.py -q`
- long_term_fix: refuser au bon endroit, à la détection, avec la vraie raison ET le vrai remède — plus un test qui vérifie que le remède proposé est effectivement accepté, sinon le message enverrait dans un mur. La détection teste tabulation, point-virgule et virgule, et la RELECTURE hérite du même choix : sans ça un fichier correctement détecté explosait ensuite dans un `pd.read_csv` nu.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_refused_csv_says_the_real_reason.py }
- rex_ref: src/dashboard/views/upload_csv.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: la contradiction était visible dans le code depuis des mois — la règle de détection cite `songs-all`, le parseur le rejette explicitement, et les deux commentaires disent la même chose correctement. Chacun avait raison séparément ; personne n'avait lu les deux ensemble.

## too-many-charts-competing-for-one-decision
- status: guarded
- severity: P3
- kind: deterministic
- symptom: une vue s'ouvre sur un mur de graphiques. Aucun n'est faux, aucun n'est de trop pris isolément, et l'utilisateur ne sait pas où regarder.
- root_cause: le motif de correction — `ui.secondary_analyses()`, un dépliant appliquant « une décision par écran » — a été écrit le 2026-08-12, le jour même où un artiste en test a dit « réduire le nombre de graphs qui permettent de prendre décision », avec la remarque citée dans son propre commentaire de module. Onze jours plus tard il était appliqué sur quatre sites et sur **aucune** des cinq vues les plus denses : Road to Algo (~35 figures), Data Wrapped (9), Créatives (8), Meta Ads (8), Prévisions (6). Le correctif existait, le diagnostic était juste, et la distance entre les deux n'était mesurée nulle part.
- signature: `python3 -m pytest tests/test_a_view_opens_on_one_decision.py -q`
- long_term_fix: un garde compte les graphiques rendus au PREMIER ÉCRAN — hors `secondary_analyses` et hors `st.expander` — et plafonne à 5 par fichier (Few : un tableau de bord tient dans un coup d'œil). Rien n'interdit d'en avoir beaucoup ; il faut seulement qu'ils ne soient pas tous dépliés d'emblée. Le repli vit DANS la fonction qui dessine, pas chez son appelant : un second appelant la rendrait sinon dépliée — et c'est ce que la première version faisait, jusqu'à ce que le garde refuse.
- autofix: none
- guard: { type: pytest, ref: tests/test_a_view_opens_on_one_decision.py }
- rex_ref: src/dashboard/utils/ui.py
- first_seen: 2026-08-23
- History:
  - 2026-08-23: c'est la deuxième fois de la journée qu'un correctif écrit exprès pour une remarque d'utilisateur n'était branché nulle part — l'autre étant le sélecteur Mac/Windows. Écrire le remède et le brancher sont deux gestes, et seul le premier laisse une trace dans le dépôt.

## prune-scoped-wider-than-what-it-refreshed
- status: guarded
- severity: P1
- kind: deterministic
- symptom: des données de production disparaissent, sans erreur, sans trace. Le nettoyage qui suit une collecte supprime plus large que ce que cette collecte vient d'écrire, donc il emporte le travail d'une autre.
- root_cause: `_prune_renamed_campaigns` (`src/collectors/_meta_upsert.py`) exécute `DELETE FROM <table> WHERE artist_id = %s AND campaign_name <> ALL(%s)` — le `DELETE` est scopé au LOCATAIRE, la liste de campagnes ne couvre qu'un COMPTE PUBLICITAIRE. Tant qu'un artiste n'a qu'un compte, les deux portées coïncident et le défaut est invisible. Le jour où la boucle passe sur deux comptes — le cas d'une agence, demandé par un vrai utilisateur — la passe du second efface tout ce que le premier vient d'écrire. Ce n'est pas une collision d'upsert, c'est une suppression de masse.
- signature: `python3 -m pytest tests/test_meta_ads_collector.py::TestPruneRenamedCampaigns -q`
- long_term_fix: le `DELETE` porte le même discriminant que ce qu'il vient de rafraîchir — `AND ad_account_id IS NOT DISTINCT FROM %s`. La colonne est ajoutée par `migrations/076` sur les 10 tables à la maille campagne plus les 3 tables de provenance ; elle est nullable, et `IS NOT DISTINCT FROM NULL` reproduit exactement l'ancien comportement tant que la flotte est mono-compte. **Le correctif est posé AVANT que le multi-comptes existe** : une fois la boucle livrée, le défaut n'aurait été visible qu'en constatant des données manquantes.
- autofix: none
- guard: { type: pytest, ref: tests/test_meta_ads_collector.py::TestPruneRenamedCampaigns::test_the_delete_is_scoped_to_one_ad_account }
- rex_ref: migrations/076_meta_ad_account_id.sql
- first_seen: 2026-08-23
- History:
  - 2026-08-23: la règle générale vaut au-delà de Meta — **un nettoyage doit porter exactement la même portée que l'écriture qu'il suit**. Ici l'écriture était par compte et la suppression par locataire ; les deux portées ont coïncidé aussi longtemps qu'il n'y avait qu'un compte, ce qui est la pire façon pour un défaut d'attendre. Trouvé en explorant une demande produit (« Tom gère plusieurs comptes »), pas en lisant le code de nettoyage.


## layer-written-but-never-wired
- status: guarded
- severity: P2
- kind: deterministic
- symptom: une couche que l'architecture décrit comme porteuse — validation, gestion d'erreur — existe, a des tests verts, et **aucun code de production ne l'appelle**. Le jour où on la branche, elle casse la production : ce qu'elle supposait du reste du code n'est plus vrai depuis des mois, et rien ne pouvait le signaler tant que personne ne l'appelait.
- root_cause: `src/models/meta_ads_validators.py` définissait quatre modèles Pydantic décrits par `CLAUDE.md` comme la couche de validation du projet ; seul `tests/test_validators.py` les importait. Quatre divergences avec les payloads réels s'étaient accumulées : aucun modèle ne déclarait `artist_id` (le champ du locataire, le seul dont ce dépôt ait souffert), `status` était obligatoire alors que le collecteur écrit `.get('status')`, `targeting` était typé `dict` alors que `_fetch_adsets` écrit `json.dumps(...)`, et `MetaInsight` exigeait dix métriques que Meta ne rend pas sur un objectif d'engagement. Le test passait **parce que** rien n'exécutait les modèles : il les confrontait à des payloads inventés par le test.
- signature: `python3 -m pytest tests/test_validators.py::test_the_collector_actually_calls_the_validators -q`
- long_term_fix: le garde vérifie par AST que le collecteur **importe** les quatre modèles ET appelle `_validate`. Un import mentionné dans un commentaire ne suffit pas ; débrancher la couche redevient un rouge. Corollaire de méthode : les fixtures d'un test de validation se construisent à partir de la sortie du vrai producteur, jamais à la main — sinon le test garde une forme que personne n'écrit.
- autofix: none
- guard: { type: pytest, ref: tests/test_validators.py::test_the_collector_actually_calls_the_validators }
- rex_ref: src/models/meta_ads_validators.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: deuxième module de la même forme trouvé le même jour — `src/utils/error_handler.py`, importé par son seul test. Verdict opposé et pour une raison mécanique : ses trois fonctions interpolent l'exception brute, donc le câbler rouvrait la classe de fuite. Retiré. **Une couche débranchée n'est pas neutre, elle pourrit** : plus elle attend, plus la brancher devient dangereux, et « on la câblera plus tard » est ce qui a coûté les quatre divergences ci-dessus.

## absence-rendered-as-a-measurement
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un graphique ou un tableau affiche `0` là où la donnée dit « aucune observation ». Le lecteur y lit une mesure — « 0 % de chance » — c'est-à-dire l'inverse de « on ne sait pas ». Aucune erreur, aucune trace : le rendu est parfaitement réussi.
- root_cause: `pdf_charts.pi_gate` (`src/dashboard/utils/pdf_charts.py`) calculait `float((data.get(b) or {}).get("prob") or 0)`. L'idiome `or 0` confond `None` (jamais mesuré) et `0` (mesuré à zéro). Cas réel dans `machine_learning/models/v3/threshold_tables.json` : Release Radar, panier « 50+ », `prob: null`, `n: 0` — dessiné comme une barre à 0 % dans un PDF envoyé à des tiers. Volet jumeau : le graphique n'affichait pas l'effectif, si bien que 66,7 % mesuré sur **3** titres s'affichait aussi haut et aussi net que 99,4 % sur 172.
- signature: `python3 -m pytest tests/test_an_empty_bracket_is_not_a_zero.py -q`
- long_term_fix: un panier sans observation n'est pas dessiné (alpha 0), un panier peu peuplé est atténué, et l'effectif `n` est écrit sous chaque barre. Le garde lit **les barres réellement produites** (hauteur et alpha), pas le code qui les produit : c'est le seul niveau où « la barre est-elle dessinée ? » a une réponse. Un `0` mesuré sur un effectif réel reste affiché en pleine intensité — l'effacer perdrait une information.
- autofix: none
- guard: { type: pytest, ref: tests/test_an_empty_bracket_is_not_a_zero.py }
- rex_ref: src/dashboard/utils/pdf_charts.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: trouvé en cherchant la réponse à une question de l'auteur des notes de test (« le taux de trigger, quelle métrique fait foi ? »), pas en auditant le graphique. La question portait sur la définition ; c'est le rendu qui était faux.

## counter-includes-our-own-robots
- status: guarded
- severity: P3
- kind: deterministic
- symptom: un compteur affiché à des visiteurs — « N artistes utilisent le produit » — inclut les comptes de service que nous créons nous-mêmes. Le nombre est faux, et le lecteur n'a aucun moyen de le recouper.
- root_cause: `live_pulse.get_registered_count_public` et `get_live_pulse` (`src/dashboard/utils/live_pulse.py`) et le KPI admin (`src/dashboard/views/admin.py`) comptaient `SELECT COUNT(*) FROM saas_artists WHERE active = TRUE`. Le canari de surveillance porte `is_canary = TRUE` depuis la migration 064 et `credential_loader.load_all_artists(exclude_canaries=True)` faisait déjà la distinction — les compteurs, non. Le plus exposé des trois est sur la **page d'inscription publique**.
- signature: `python3 -m pytest tests/test_public_counters_count_humans.py -q`
- long_term_fix: le prédicat « ce qui compte comme un locataire humain » est une constante unique (`live_pulse._HUMAN_TENANTS`), et le garde inspecte par AST le SQL réellement exécuté — en **résolvant les constantes de module interpolées**, sans quoi il déclarerait absent un prédicat qui est là.
- autofix: none
- guard: { type: pytest, ref: tests/test_public_counters_count_humans.py }
- rex_ref: src/dashboard/utils/live_pulse.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: le même fichier montrait le nom d'artiste du **propriétaire de la plateforme** comme valeur d'exemple du champ « Nom d'artiste », à chaque inscription. Même famille : une valeur interne qui fuit vers une surface publique parce que personne ne relit cette surface **en tant que visiteur**.

## leak-via-an-exception-received-as-an-argument
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un credential part dans un journal, un mail ou une base, depuis un module que le garde anti-fuite ne surveille pas — et il a raison de ne pas le surveiller selon sa propre question.
- root_cause: `test_credentials_security.py::test_no_probe_surfaces_a_whole_exception` demande « une exception née d'un appel HTTP peut-elle atteindre ce module ? » et répond en suivant le **graphe d'imports**. C'est juste pour une exception capturée sur place, et aveugle à celle qu'on reçoit en ARGUMENT : `error_alert._maybe_email(page, exc)` (`src/dashboard/utils/error_alert.py`) n'importe aucun client HTTP et n'en est importé par aucun, et envoyait la traceback complète **par Brevo**, un tiers, dans une boîte mail. Le message d'une exception `requests` embarque l'URL préparée — donc `access_token=`, `key=`.
- signature: `python3 -m pytest tests/test_an_exception_passed_as_an_argument_is_redacted.py -q`
- long_term_fix: un second garde, avec un prédicat qui épouse la vraie question — *cette fonction met-elle dans une chaîne une exception qu'elle n'a pas attrapée ?* Il repère les paramètres portant une exception (nom conventionnel ou annotation) et les variables issues d'un `traceback.format_*`, et exige un emballage (`redact` / `safe_error`). Sur `src/`, `airflow/` et `tools/`, il ne trouvait que deux sites — la précision du prédicat est ce qui rend le garde utilisable.
- autofix: none
- guard: { type: pytest, ref: tests/test_an_exception_passed_as_an_argument_is_redacted.py }
- rex_ref: src/dashboard/utils/error_alert.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: **septième fois que la portée d'un garde est le défaut**, et la première où l'élargir au graphe d'imports n'aurait rien donné — l'appel passe par un argument, qui ne laisse aucune trace dans ce graphe. Un élargissement bidirectionnel a été essayé et mesuré : 39 → 57 modules et 6 modules « en faute » dont la plupart ne manipulent que des exceptions de base de données. Le prédicat large aurait produit 25 corrections sans valeur ; le prédicat juste en a produit 1.

## format-marker-in-a-plain-string
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un marqueur `{...}` destiné à une f-string se retrouve dans une chaîne ordinaire et part **tel quel** dans le SQL. Postgres reçoit huit caractères littéraux au lieu d'un prédicat — soit une erreur de syntaxe, soit, quand le marqueur est optionnel, un filtre qui ne filtre rien.
- root_cause: en ajoutant le filtre de compte publicitaire aux vues Meta, une requête de `src/dashboard/views/meta_creatives.py` a reçu `{acct}` sans que le `f` soit ajouté au littéral. `ruff` ne le voit pas (une chaîne avec des accolades est valide), un test de rendu non plus (la vue ne s'affiche qu'avec deux comptes déclarés, et la flotte est mono-compte).
- signature: `python3 -m pytest tests/test_meta_multi_account.py::test_no_account_marker_survives_in_a_plain_string -q`
- long_term_fix: garde AST restreint aux arguments passés **directement** à `fetch_df` / `fetch_query` / `execute_query` — une constante de module marquée puis `.format()`-ée plus loin est légitime, et un garde qui la signalerait serait désactivé dans la semaine.
- autofix: none
- guard: { type: pytest, ref: tests/test_meta_multi_account.py::test_no_account_marker_survives_in_a_plain_string }
- rex_ref: src/dashboard/utils/meta_accounts.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: défaut commis pendant l'écriture de la brique, pas hérité. Le garde a été écrit dans la foulée et vu rouge sur le défaut réel avant d'être vert.

## audit-reads-the-constraints-not-the-installed-set
- status: guarded
- severity: P3
- kind: deterministic
- symptom: l'audit de vulnérabilités rend un rapport propre pendant que le parc réellement installé porte des dizaines d'avis. Il lit un fichier de **contraintes** (des planchers `>=`) que rien n'installe tel quel.
- root_cause: `.github/workflows/security-nightly.yml` exécutait `pip-audit -r requirements.txt`. Ce fichier porte des planchers (`weasyprint>=62.0`, `cryptography>=42.0.0`), donc pip-audit résolvait des versions récentes — pendant que la CI installait `uv.lock` via `uv sync --frozen`, qui épinglait `pyjwt 2.12.1` (notre authentification), `starlette 1.0.0`, `python-multipart 0.0.28` : **127 avis sur 18 paquets**.
- signature: `! grep -nE 'pip-audit -r requirements.txt' .github/workflows/security-nightly.yml`
- long_term_fix: l'audit résout le lock avant de le lire — `uv export --frozen --no-dev --no-hashes` — donc il regarde exactement ce que `uv sync --frozen` installe. Règle générale : **on n'audite jamais un fichier de contraintes, on audite l'ensemble résolu**.
- autofix: none
- guard: { type: ci-step, ref: .github/workflows/security-nightly.yml }
- rex_ref: .github/workflows/security-nightly.yml
- first_seen: 2026-08-24
- History:
  - 2026-08-24: après régénération du lock, 127 avis sur 18 paquets → 12 sur 2. Les deux restants sont assumés : `apache-airflow` (pin délibéré sur la version de l'image Docker, suivi en R49b) et `ecdsa` (sans correctif amont).


## validation-bound-invented-not-read-from-the-schema
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un validateur qui **lève** refuse une donnée parfaitement légitime, parce qu'une de ses bornes a été tapée à la main au lieu d'être lue dans le schéma. La collecte du locataire s'arrête, et le message parle d'une limite qui n'existe nulle part.
- root_cause: `src/models/meta_ads_validators.py` déclarait `max_length=255` sur `campaign_name`, `adset_name` et `ad_name`. Les colonnes correspondantes sont des `text`, sans limite, et la production contient une campagne de **313 caractères** (nom généré, avec emoji). Le modèle venait d'être branché (R47) et **lève** : la première collecte Meta de ce locataire se serait arrêtée. Second cas dans le même fichier : `targeting` typé `str` alors que la colonne est `jsonb` — le collecteur y écrit `json.dumps(...)` et psycopg2 le relit en `dict`, donc 69 lignes sur 69 étaient refusées à la relecture.
- signature: `python3 -m pytest tests/test_the_validators_accept_what_production_holds.py -q`
- long_term_fix: le garde confronte les modèles aux **lignes réelles déjà en base** — un modèle qui refuse ce que la production contient déjà refusera le même payload la nuit suivante — et un second test, sans base, interdit toute borne de longueur qu'aucune colonne ne porte. Règle générale : **une borne de validation se lit dans le schéma, elle ne s'invente pas** ; si une vraie limite apparaît, la lire dans `information_schema`.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_validators_accept_what_production_holds.py }
- rex_ref: src/models/meta_ads_validators.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: trouvé **avant tout déploiement**, en confrontant délibérément les modèles fraîchement branchés aux lignes de la base. Les tests unitaires du modèle ne pouvaient pas le voir : ils lui présentent des payloads écrits à la main, donc courts et propres. Corollaire de méthode : quand on branche une validation qui lève, la première chose à faire est de lui montrer la production.

## empty-table-rendered-as-health
- status: guarded
- severity: P3
- kind: deterministic
- symptom: un panneau affiche « ✅ tout va bien » à partir d'une requête qui ne rend rien — alors que « rien » a deux causes opposées : il n'y a effectivement aucun problème, ou **personne n'écrit jamais dans cette table**.
- root_cause: `views/alerts.py::_section_circuit_breakers` et `views/etl_logs.py` interrogent `etl_circuit_breaker` avec `WHERE state != 'closed'` et affichaient `st.success("✅ … fonctionnement normal")` sur zéro ligne. Or `CircuitBreaker` (`src/utils/circuit_breaker.py`) n'a **aucun appelant de production** — il n'est instancié que dans son propre exemple de docstring et dans son helper `reset_circuit` — et la table est vide. Les deux panneaux affirmaient une bonne santé qu'aucune mesure ne soutenait, dont un sur la page d'alertes.
- signature: `python3 -m pytest tests/test_an_empty_table_is_not_a_clean_bill_of_health.py -q`
- long_term_fix: `circuit_mechanism_is_recording(db)` répond à « cette table est-elle écrite ? », et le ✅ y est conditionné ; sinon le panneau dit explicitement qu'il ne prouve rien et renvoie vers la mesure qui fait foi (la fraîcheur). Le garde repère par AST un `st.success` dans la branche « aucune ligne » d'une fonction qui interroge cette table.
- autofix: none
- guard: { type: pytest, ref: tests/test_an_empty_table_is_not_a_clean_bill_of_health.py }
- rex_ref: src/utils/circuit_breaker.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: la classe a été balayée sur les 41 vues — **16 sites** « aucune ligne → ✅ », dont **un seul** est en faute. Les 15 autres lisent des tables réellement écrites (`etl_run_log`, `saas_users`, `artist_subscriptions`), où « aucune ligne » est une vraie mesure. Corriger les 16 aurait été du bruit ; l'incidence se mesure avant de généraliser, comme pour l'élargissement du garde anti-fuite le même jour.
  - 2026-08-24: défaut jumeau corrigé dans le même module — le contrat du circuit breaker prescrivait littéralement `cb.record_failure(str(e))` dans sa docstring, et cette chaîne est **persistée** (`last_error`, 500 car.) puis **affichée**. Aucun DAG ne l'appelait, donc rien n'a fuité, mais le premier à suivre la documentation aurait écrit le token partagé en base. `record_failure` rédige désormais **à l'entrée** : compter sur les appelants marche jusqu'au premier qui copie l'exemple.


## guard-seeded-by-prose-not-by-code
- status: guarded
- severity: P3
- kind: deterministic
- symptom: un garde marque en faute un module qui vient d'appliquer son propre correctif. Le module ne fait rien de risqué : il a seulement **importé le remède**, et le remède est marqué dangereux parce que sa documentation nomme le danger.
- root_cause: `tests/test_credentials_security.py::_modules_that_call_http` amorçait sa portée en cherchant `"requests."`, `"googleapiclient"`, `"urlopen"` **en sous-chaîne dans le texte du fichier**, docstrings comprises. `src/utils/safe_error.py` — dont le rôle est précisément de rédiger ces messages — nomme les deux APIs dans sa prose pour expliquer pourquoi il existe. Il était donc « touche un client HTTP », et **tout module l'important héritait de la marque**. Mesuré le 2026-08-24 : ajouter `from src.utils.safe_error import redact` à `circuit_breaker.py` l'a fait entrer dans la portée et échouer sur trois lignes sans rapport.
- signature: `python3 -m pytest tests/test_credentials_security.py -q`
- long_term_fix: la graine est lue par **AST** (`_calls_http`) — import du client, accès à un de ses attributs, appel à `urlopen` — jamais en texte. Une mention en commentaire n'est pas un appel. Et parce que corriger un faux positif ne doit pas coûter de la vraie couverture, une **seconde graine** a été ajoutée : importer `src.utils.safe_error` est un aveu (ce module formate des exceptions porteuses de credentials, sinon il n'irait pas y chercher `redact`). Sans elle, la correction faisait tomber 19 modules hors de portée — 40 → 21. Un `_SCOPE_FLOOR` garde désormais la taille de la portée.
- autofix: none
- guard: { type: pytest, ref: tests/test_credentials_security.py::test_the_http_scope_does_not_silently_shrink }
- rex_ref: tests/test_credentials_security.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: **un garde qui punit l'application de son propre remède finit désactivé** — c'est la forme la plus coûteuse du faux positif, parce qu'elle décourage exactement le geste qu'on veut encourager. Et la correction a failli créer le défaut inverse : la portée passait de 40 à 21 modules en silence, ce qui est la 7ᵉ occurrence de « la portée d'un garde est le défaut », dans le sens du rétrécissement cette fois. D'où le plancher.


## boundary-with-no-named-exit-kills-what-must-pass
- status: guarded
- severity: P2
- kind: deterministic
- symptom: une frontière posée pour borner le rayon de souffle de la suite éteint aussi **ce qui doit sortir**. Le composant tué est un moniteur : son rouge quotidien se lit comme du bruit, et personne ne remarque qu'il ne mesure plus rien.
- root_cause: `tests/conftest.py::_no_real_http` est `autouse` et refuse toute connexion sortante sur 80/443, sans exception nommée. `tests/test_prod_health.py` — dont le rôle est de sonder l'application LIVE **à travers Cloudflare**, l'une des trois épaisseurs du filet de surveillance, celle qui voit ce que les contrôles internes ne voient pas (le 403 Bot Fight Mode du webhook Stripe, 2026-06-14) — rendait **14 failed, 14 errors** chaque matin depuis le 2026-08-23. La suite se gardait pourtant déjà elle-même (`RUN_PROD_HEALTH=1`, sinon skip, « so a push never hammers prod ») : la frontière l'écrasait au niveau SOCKET, sous son propre garde.
- signature: `python3 -m pytest tests/test_the_http_escape_hatch_stays_narrow.py -q`
- long_term_fix: une sortie **nommée et unique** — `@pytest.mark.real_http`, consultée par la frontière, déclarée dans `pyproject.toml`. Deux gardes l'encadrent : la liste des fichiers autorisés est explicite (une échappatoire qui se propage redevient l'absence de frontière), et la frontière doit continuer de consulter le marqueur. Règle générale : **une frontière `autouse` sans exception nommée n'est pas une frontière, c'est un interrupteur** — poser la sortie en même temps que la frontière, pas après.
- autofix: none
- guard: { type: pytest, ref: tests/test_the_http_escape_hatch_stays_narrow.py }
- rex_ref: tests/conftest.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: le marqueur n'a pas pris du premier coup — `test_prod_health.py` affectait DÉJÀ `pytestmark`, et une seconde affectation **écrase la première sans avertissement**. Le marqueur perdu ne manque à personne : il cesse simplement de s'appliquer. Garde ajouté sur les 150 fichiers de test : `pytestmark` s'affecte au plus une fois.
  - 2026-08-24: le garde de portée de l'échappatoire a lui-même commencé en cherchant `"real_http" in source`, et accusait le méta-test voisin qui ne fait que **nommer** la fixture `_no_real_http`. C'est `guard-seeded-by-prose-not-by-code`, cataloguée une heure plus tôt le même jour et aussitôt réintroduite. Le réflexe du `in source` est tenace ; sur une question qui porte sur du code, la réponse est l'AST.


## dead-argument-from-a-major-version-ago
- status: guarded
- severity: P2
- kind: deterministic
- symptom: un paramètre d'une version majeure précédente traîne dans le code. Il ne fait **rien** sur la version qui tourne, donc rien ne le signale — et il rend la montée de version impossible, ce qu'on découvre le jour où on la tente.
- root_cause: les 16 DAGs portaient `schedule_interval=` (l'orthographe d'Airflow 1/2.3, remplacée par `schedule=` en 2.4) et 7 d'entre eux `provide_context=True` (un argument d'Airflow **1.x**, sans effet depuis la 2.0 où le contexte est passé automatiquement). Airflow 2.8.1 — la version de production — les accepte en silence ; Airflow 3 les **rejette**. Conséquence directe : la PR Dependabot #100 (`apache/airflow` 2.8.1 → 3.3.0), ouverte depuis le 2026-08-01 et qui ressemble exactement au correctif de sécurité attendu, aurait fait échouer l'import des **16** DAGs, donc arrêté toute la collecte.
- signature: `python3 -m pytest tests/test_every_dag_imports.py -q`
- long_term_fix: les deux vestiges sont retirés (aucun changement de comportement en 2.8.1), et un garde importe **réellement les 16 DAGs** à chaque exécution de la suite. Ce garde n'était pas possible avant : ces mêmes vestiges rendaient l'import impossible hors conteneur, et ce dépôt le documentait comme une fatalité — « aucun DAG n'est importable hors conteneur », donc les seuils de collecte avaient dû être déplacés dans `src/utils/` pour être testables du tout.
- autofix: none
- guard: { type: pytest, ref: tests/test_every_dag_imports.py }
- rex_ref: airflow/dags/meta_ads_api_daily.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: la contrepartie mérite d'être nommée — **le blocage était aussi ce qui empêchait de le voir**. Tant que les DAGs ne s'importaient pas, aucun test ne pouvait dire qu'ils étaient cassés pour la version suivante, et la note « c'est comme ça » a tenu des mois. Retirer deux mots-clés morts a rendu 16 DAGs testables et débloqué R49b du même coup.


## session-wide-stub-of-an-installed-package
- status: guarded
- severity: P2
- kind: deterministic
- symptom: des tests passent ou échouent selon l'ORDRE d'exécution. Isolés ils sont verts ; groupés, quatre d'entre eux tombent sur « n'est pas un paquet ». Et, plus discrètement, des tests qui croient exercer un vrai client travaillent contre un mock.
- root_cause: `tests/test_e2e_two_tenants.py` et `tests/test_collectors_errors.py` posaient `sys.modules["spotipy"] = MagicMock()`, idem pour `googleapiclient`, `airflow`, `airflow.operators` — **à l'import du fichier, donc dès la COLLECTE**, et sans jamais restaurer. La justification écrite (« ils vivent dans l'image Airflow, pas dans le venv de dev ou de CI ») a cessé d'être vraie sans que personne le remarque : les quatre paquets sont des dépendances déclarées et installées. `airflow.operators` devenu MagicMock, tout `from airflow.operators.empty import EmptyOperator` ultérieur échouait.
- signature: `python3 -m pytest tests/test_no_test_stubs_an_installed_package.py -q`
- long_term_fix: les stubs obsolètes sont retirés (les paquets existent, les imports résolvent), et un garde vérifie par AST qu'aucun fichier de test ne remplace un paquet **installé** par un mock. Le prédicat porte bien sur la question — le stub reste légitime pour un paquet réellement absent, et un garde qui l'interdirait partout serait contourné.
- autofix: none
- guard: { type: pytest, ref: tests/test_no_test_stubs_an_installed_package.py }
- rex_ref: tests/test_e2e_two_tenants.py
- first_seen: 2026-08-24
- History:
  - 2026-08-24: la justification du stub était datée, pas fausse à l'origine — et c'est ce qui rend la classe pénible : **rien ne relit un commentaire quand l'environnement change**. Ici le changement d'environnement était l'installation d'Airflow dans le venv, et le stub a survécu des mois à sa raison d'être, en cassant les imports des autres.
  - 2026-08-24: retirer le stub d'`airflow` a rendu `test_e2e_two_tenants` plus fidèle, pas moins : les opérateurs sont désormais construits pour de vrai, donc une erreur de structure du DAG est vue dans la suite plutôt qu'au réveil du scheduler.
