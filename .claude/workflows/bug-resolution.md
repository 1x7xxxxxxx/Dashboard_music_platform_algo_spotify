---
keywords: bug, bogue, régression, regression, drift, silent failure, silently, silencieux, silencieuse, broken, broke, cassé, casse, ne fonctionne pas, ne marche pas, crash, plante, plantage, traceback, exception, échoue, échec, corruption, corrompu, clobber, overwrote, overwrite, écrasé, écrase, desync, désync, désynchronisé, incohérent, incohérence, stale, obsolète, périmé, orphaned, orphelin, red test, test rouge, tests rouges, failing test, went red, root cause, root-cause, cause racine, hotfix, data loss, perte de données, faux positif, false positive, comportement inattendu, unexpected, résultat faux, 500, wedge, wedged
strong_keywords: traceback, stacktrace, corruption, corrompu, data loss, perte de données, silent failure
rex: []
---

# Workflow — bug resolution

The default flow when a bug, regression, drift, or silent failure is identified. It is a **playbook the
model executes**, NOT wired automation. Each step names its carrier and its invocation TYPE:
`playbook` (model discipline), `hook` (fires automatically), `signature`, `pytest`, `human`.
A step that looks automatic but cannot be is marked as such — never disguised.

| # | Step | Carrier | Type |
|---|------|---------|------|
| 0 | ~~a hook launches the pipeline~~ | **IMPOSSIBLE.** A hook observes; it cannot spawn an agent. `inject_context.py` injects THIS file on the keywords above — the model then runs it. | ❌ observe-only |
| 1 | Bug identified | the model, in context (the harness cannot detect "a bug was found") | playbook |
| 2 | Whole-repo impact sweep | `.claude/skills/impact-analysis/SKILL.md`. The bug is an INSTANCE OF A CLASS: find every sibling before fixing one. | playbook |
| 3 | Seen before? | grep `.claude/dev-docs/error-classes.md` + ADRs + `DEVLOG.md` + `git log` | playbook |
| 4 | Sweep every catalogued class | `python3 .claude/scripts/audit_runner.py --deterministic` | signature |
| 5 | Root-cause by READING the code | never from a guess about what is wrong | playbook |
| 6 | Challenger — if it touches a high-stakes surface | `code-critic`, mandatory (see below). Treat **REJECT as blocking**. | playbook |
| 7 | Fix **+ a durable guard** | guard = a signature in `error-classes.md` (exit ≠ 0 = hit), and/or a test, and/or a hook | playbook |
| 8 | **Mutation-verify the guard** | re-introduce the defect and watch the guard go RED. **A test never seen fail is not a guard.** | pytest |
| 9 | Silent-failure sweep — if a background job or stream consumer | `silent-failure-hunter` where it exists | playbook |
| 10 | Security — if an endpoint, credential, or external surface | `security-reviewer` + the `pre_commit_scan.py` hook | playbook + hook |
| 11 | Deploy sync — if schema or deploy | a forward migration, never a manual edit on the target; then checksum repo↔target | playbook |
| 12 | REX drafted → promoted | `draft_rex.py` (Stop hook) writes `pending-rex.md`; `/retro` promotes (**a human writes the lesson**) | hook + human |
| 13 | ROADMAP updated | `.claude/dev-docs/roadmap/checklist.md` (actif) — a finding enters **only with the command that measured it**. Fixed and shipped? `Spawn roadmap-keeper` rotates it into `archive.md` | playbook |

**The carriers that are NOT the model:** step 4 (`audit_runner`, a signature), step 8 (`pytest`),
step 12's draft (a Stop hook). Everything else is model discipline — which is exactly why it is
written down: discipline that is not written is discipline that is skipped under time pressure.

## High-stakes surfaces — `code-critic` FIRST, before writing the code

Not before committing it. Before writing it: a design that looks additive is exactly where the
dangerous flip hides, and by commit time the sunk cost argues for shipping.

Adapt this list to the repository — the shape is what transfers, not the items:

- anything a **human reads as a verdict** (a safety state, an alert, a status badge, a score)
- a **schema change** or any migration that reaches a deployed environment
- a **deploy or ops script** that mutates a live target
- a **gate** — a promotion rule, a CI threshold, a quality bar
- the **hot path** — anything that can block, wedge, or reorder writes
- **money, credentials, destruction, external effects** — the irreversible tier

Evidence this is not ceremony: a dashboard showed a green **OK** for a signal that was not wired at
all, because the store's BOOLEAN type has no NULL. Tests were green. The panel had a careful
description. Only an adversarial read of "what does this display when the signal is absent?" found
it. **A test only checks the cases someone imagined.**

## Anti-patterns this flow exists to prevent

- Fixing the reported instance and leaving the siblings live (step 2).
- Shipping a guard nobody ever saw fail (step 8).
- Writing a status note the code disproves — re-read the code, do not trust the note (step 5).
- Announcing a number that was not just measured.
- Measuring an **artifact** where the question is an **effect**: a file that exists, a hook that
  exits 0, a chain that is "present". Ask what the thing is supposed to *do*, then run that.
