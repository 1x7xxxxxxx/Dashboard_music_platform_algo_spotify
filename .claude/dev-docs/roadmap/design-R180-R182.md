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
