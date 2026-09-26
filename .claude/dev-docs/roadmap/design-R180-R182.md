# Design — R180 · R181 · R182 (error families, nightly recap, baseline brick)

Type: Doc (design submitted to `code-critic` BEFORE any code, 2026-09-26)
Uses: `.claude/dev-docs/error-family-rules.md`, `.claude/dev-docs/error-class-families.md`
Persists in: this file; verdicts recorded at the bottom

## R180 — family membership DECLARED, one detector or probe per rule

**Today.** `tools/dev/error_class_families.py` assigns a class to a family by a REGEX on its
id + symptom (e.g. `tenant|artist[_-]id|…`). That is the "predicate that matches a form, not
a property" defect the catalogue itself names; a class can match 0, 1 or 2 regexes.

**Change.**
1. Add `- family: <slug>` to every class entry in `error-classes.md`. Seeding: a one-off
   script proposes the family the current regexes give; ambiguous (0 or ≥2 matches) classes
   are listed for a human-grade review (by me, reading the entry), never auto-assigned.
2. `error_class_families.py` reads the DECLARED field; the regexes stay only as a lint that
   flags a declaration contradicting every regex (report, not block).
3. Admission (`audit_runner.py --admission`) additionally refuses a NEW class without a
   valid `family:` (one of the 18 slugs).
4. Per rule, the "caught at" column of `error-family-rules.md` becomes a checked link: each
   family row names ≥1 existing test file (commit) or nightly job/task (night), and a pytest
   verifies each named path exists and that no family is left with neither — families that
   honestly have no mechanical detector are declared `review-only` explicitly.

Out of scope: rewriting the 418 guards; merging classes.

## R181 — one recap mail per night

**Today.** Up to four automated mail sources: `alert_monitor` (prod, 23:00, only when issues),
`security-nightly` notify (GitHub, per night when a job failed), `ci_break_mail` (GitHub, per
green→red transition), `prod-health` (GitHub, when red). The owner reads none of them.

**Change.** `alert_monitor.send_consolidated_alert` (prod) gains a "GitHub" section built by
a pure function from the public Actions API (no token — the repo is public; unauthenticated
limit 60 req/h, we need 3): latest conclusion of `ci.yml` on main, `security-nightly.yml`,
`prod-health.yml`, each with its run link. The recap is sent EVERY night (a quiet night =
one short "all green" mail, so silence means the monitor is dead — see
`test_a_quiet_night_sends_nothing`, which must be revisited: its premise was "quiet = no
mail"). The GitHub-side mailers stay (a red main still mails once, immediately) — the recap
is the daily floor, not a replacement. Network failure to GitHub → the section says
"GitHub illisible", never "green".

Risk named: changing "quiet night sends nothing" is a product decision the owner took
("un mail récap par nuit pour commencer").

## R182 — `deployment-baseline-rev1`, brick "error class management"

A NEW private GitHub repo (name without accent/dot for tooling), containing only this brick:
- `rules/error-family-rules.md` — the 18 rules rewritten project-agnostic (no streaMLytics
  names), each with its question and "caught at".
- `tools/` — generic copies: `select_tests.py` (with the meta-guard rule),
  `night_run.py` subset (status/check incl. CI verdict + mail-journal age),
  `check_durations_are_collectable.py --fix`, `ci_break_mail.py` (cancelled ≠ red),
  catalogue tooling (`error_class_health.py`, `error_class_families.py`) parametrised by path.
- `starter-guards/` — project-agnostic self-proving guards: a proof must call its detector;
  structure-not-text inventory; generated-document `--check` in pytest; central secret wins
  over stored copy (as a pattern, with a fixture); naive datetime vs aware column.
- `install.sh` — copies the brick into a target repo, idempotent, refuses to overwrite
  local edits (prints a diff).
- CI of the brick itself: an EMPTY sample project is created, `install.sh` runs, and the
  starter guards pass (and one fabricated defect per guard turns them red).
Then `claude_code_deployment_baseline` gets a pointer + REX entries (R21+) — not a copy.

Out of scope for rev1: other thematic bricks (the owner will add them later).

## Verdicts (code-critic)

code-critic, 2026-09-26 :
- **R180 — BUILD-MODIFIED.** `classify()` stops at the FIRST regex hit, so « ≥2 matches » can
  never surface: enumerate all candidates before seeding. A « caught at » check that only
  tests a path exists is a form, not detection: require a self-proof in the named test.
- **R181 — BUILD-MODIFIED.** Repo confirmed PUBLIC. The quiet-night branch of
  `send_consolidated_alert` has NO test (`test_a_quiet_night_sends_nothing` tests another
  helper): pin it before changing it. Mark incidents already mailed by the GitHub-side
  mailers « déjà signalé ».
- **R182 — DO-NOT-BUILD as a new repo.** The baseline already distributes by presets, already
  has the empty-project self-test (`bench/`), and already tracks drift between tool copies:
  a third lineage would drift. Build an `error-classes` PRESET inside the existing baseline.
  **Owner chose the preset.**


## R184–R186 (2026-09-26) — probe the whole error-management chain, and bind the sweep to its class

## Context
The owner asks: (1) test the whole error-class management chain with probes, say if it
works, and which unit tests guarantee it; (2) run it nightly if relevant; (3) confirm that a
class without a whole-repo impact analysis and a root-cause analysis is refused by a red test;
(4) put the actions in the roadmap.

Exploration (2026-09-26) answered (3) — **partly yes**. Refused today, in CI:
- no `root_cause` → `tests/test_every_error_class_is_complete.py::test_a_class_names_its_cause_and_its_end`
- `cause_evidence` missing/inferred → `test_the_error_class_health_only_improves.py::test_no_hole_counter_ever_grows` (ceilings `cause_unknown` 7 — already full, `cause_inferred` 0)
- `siblings:` missing / `not-swept` → same counter test (`siblings_never_swept` ceiling 0); stale JSON → `error_class_health.py --check` (ci.yml:276)
- a `swept:` without a bold count, or one that only re-ran the guard → `audit_runner --sweep-verdict` (ci.yml:234)
- no family / no admission ticket → `audit_runner --admission` (ci.yml:223)
- a Claude-Code commit adding a class with no sibling-sweeper/engineering-loop call in 48 h → hook `require_sweep_before_catalogue.py` (tests: `test_the_catalogue_needs_a_real_sweep.py`)

NOT refused: the sweep is not bound to THE class (any sweep in 48 h counts); a terminal
`git commit` skips the hook; `root_cause` needs only 4 characters; `cause_evidence: read` is a
label; `sites:N` ticket is never compared to the sweep's count; two refusals depend on
ceilings already full (`cause_unknown` 7, `guard_does_not_prove_itself` 34) — raising a
ceiling silently removes the refusal; `check_error_class_evidence.py` only warns, untested;
`--prose` has no pytest guard. Owner chose **« bound to the class »**.

## R184 — an end-to-end probe of the chain (the EFFECT, not the artifact)
New `tools/dev/probe_error_management.py` (pure probe list + runner). For each gate it
fabricates ONE defective class in a temp copy of the catalogue (or a temp git repo for the
hook), runs the REAL gate, and requires it red; then the clean control must be green:

| probe | fabricated defect | gate run |
|---|---|---|
| no family / bad family | `family:` removed / `family: nope` | `audit_runner --admission` → rc 2 |
| no ticket, `sites:1` | new class, no `admitted:` / `sites:1` | `--admission` → rc 2 |
| no sweep | `siblings: not-swept`, then field absent | `error_class_health` counters vs ceilings |
| sweep = guard rerun / no bold count | `siblings: swept:… re-ran the guard` | `--sweep-verdict` → rc 1 |
| no root cause / inferred / unknown evidence | field removed / `inferred` | completeness test + counters |
| never seen red | `seen_red: never` on a new class | new per-class rule (R185) |
| stale generated docs | edit catalogue, keep docs | `error_class_health --check`, `error_class_families --check` |
| commit without sweep | temp repo, catalogue diff, empty transcripts | hook → exit 2; with a matching `sweep_ref` → 0 |
| terminal commit | same, via `git commit` (pre-commit hook) | exit ≠ 0 |

Output: a table probe → expected → observed → the pytest that guarantees it (the answer to
« quels unitests »). Wiring: `make error-management-probe`; pytest
`tests/test_the_error_management_chain_refuses_every_defect.py` runs the probe list (so a
gate that stops refusing turns the suite red); **nightly** job `error-management-probe` in
`.github/workflows/security-nightly.yml` (reaches `notify` like the others,
`test_a_red_nightly_job_reaches_the_owner.py` covers the wiring) — relevant nightly because
the probe catches CONFIG drift (a CI step removed, a ceiling raised) that no code diff shows.

## R185 — refusals that do not depend on a ceiling (new classes only, since `admission-since`)
In `.claude/scripts/audit_runner.py --admission` (reuse `_headers`, `_admission_since`,
`_admission_verdict`), a class with `first_seen >= admission-since` is refused unless:
- `siblings:` starts `swept:` with a readable bold count (reuse `error_class_health._swept_sites`);
- `cause_evidence` ∈ {read, measured} AND `root_cause` or `cause_evidence` cites a
  `path:line` that exists in the repo;
- `seen_red` is a date or `self-proving (<file>::<test>)`;
- a `sites:N` ticket ⇔ the sweep's bold count ≥ N.
Old classes untouched (418 are grandfathered by date). Self-proving test in
`tests/test_a_new_class_justifies_its_existence.py` (fabricated classes, one per rule).
Check the 14 classes admitted since 2026-09-19 pass; fix any that do not (never delete).

## R186 — the sweep bound to its class, and no terminal bypass
- New field `- sweep_ref: <agent id>` on new classes (the sibling-sweeper / engineering-loop
  run that covered them). `require_sweep_before_catalogue.py`: for each ADDED class, its
  `sweep_ref` must name a real sibling-sweeper/engineering-loop tool_use in the project
  transcripts (reuse its transcript parser; window widened to 7 days since the id is exact);
  `SWEEP_OVERRIDE` stays, logged.
- Same check from git: `.pre-commit-config.yaml` local hook `catalogue-sweep` calling the
  hook's pure core in « git mode » (staged diff) — a terminal `git commit` is checked too.
  CI cannot read transcripts: CI checks only that a new class HAS a `sweep_ref` (in R185).
- `check_error_class_evidence.py`: add its missing test, or retire it if R185 subsumes it.
- `--prose`: add a self-proving pytest (fabricated comment-only hit).
- `/capitalise` command text + `.claude/rules` mention `sweep_ref` (the command writes it).
- Baseline preset: port R185 rules into the preset's starter family guard (skeleton classes
  get `sweep_ref: n-a (example)`), repack, self-test.

## Order & gates
R184 first (probe measures TODAY's state — some probes are expected red: « terminal commit »,
« never seen red », « bound sweep » — reported, not hidden), then R185, R186; the probe must
be all-green at the end. Each unit: code-critic on the design first (gates = high-stakes),
`make test-changed`, mutation of each new guard, commit + push, CI verdict read,
roadmap-keeper on delivery. Roadmap: R184/R185/R186 rows in `checklist.md` index (with the
measuring command), design note appended to `design-R180-R182.md`.

## Verification
- `make error-management-probe` → every probe red on its defect, green on the control.
- `pytest tests/test_the_error_management_chain_refuses_every_defect.py` green; mutate one
  gate (e.g. remove the `siblings` rule) → red.
- Temp repo: `git commit` of a class without `sweep_ref` → refused; with a real sweeper id → ok.
- `workflow_dispatch` of security-nightly → `error-management-probe` job green, reaches notify.
- Final report to the owner: the probe table + the unit tests that guarantee each refusal.


### code-critic verdicts on R184–R186 (2026-09-26) — all BUILD-MODIFIED, adopted

- **R184**: the gates' paths are module constants — resolved by running the REAL gates in a
  throwaway `git worktree` of HEAD (history included), not by patching globals. « Config drift
  that no diff shows » was overstated: a ceiling IS a diff. What a diff-routed test misses is a
  gate UNWIRED from `ci.yml` — so the probe also asserts `ci.yml` still runs each gate. The
  full probe costs minutes (one gate set per probe), so it runs NIGHTLY + `make
  error-management-probe`; the per-commit suite gets the cheap wiring assertion only.
- **R185**: refusing `cause_evidence: inferred` and `seen_red: never` contradicts rule 15
  (honest terminal states) and would reward invented dates. Adopted: `inferred` is allowed
  but must cite an existing `path:line` like `read`/`measured`; `never`/`n-a` must carry a
  reason; `swept:` with a readable count and `sites:N` ≤ that count stay as designed.
- **R186**: `sweep_ref: <agent id>` dropped — nothing guarantees the id is transcribed
  faithfully. The binding is by CONTENT instead: some sibling-sweeper / engineering-loop call
  in the window must mention (prompt or result) at least one path the new class cites. The
  pre-commit « git mode » diffs the INDEX (`git show :path`) against HEAD, not the working tree.
