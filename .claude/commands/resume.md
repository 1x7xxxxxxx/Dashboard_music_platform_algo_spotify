---
rex:
  - date: 2026-08-03
    issue: "Steps 1 and 5 read `.claude/dev-docs/ROADMAP.md`, an unrendered bootstrap template whose Current Sprint and ADR sections held only TODO placeholders. Real open work lived in roadmap/checklist.md, real ADRs in docs/adr/ — so /resume rebuilt session context from nothing."
    fix: "Repointed to the two-file roadmap (checklist.md actif) and to docs/adr/ for the ADR scan."
    ref: "roadmap-two-files-2026-08-03"
    severity: crit
---

Resume the current session context after a /clear or session restart.

## What to do

1. Read `.claude/dev-docs/roadmap/checklist.md` — the **active** roadmap. Extract the
   `## 🔖 REPRISE` block (current state, read first) and **BOTH index tables** :
   `## 📋 Tâches ouvertes` *and* `## 🙋 En attente de toi`.
   Do not read `archive.md`: it holds only what already shipped.

   ⚠️ **Les deux tables, pas une.** Cette consigne n'en nommait qu'une jusqu'au
   2026-09-17. Une tâche qui attend un geste humain est OUVERTE — elle n'est
   simplement pas commençable par une séance — et `/resume` annonçait « aucune tâche »
   sur un dépôt qui en avait une. Le même défaut existait dans `tools/dev/night_run.py`,
   corrigé le même jour : classe `a-status-screen-that-reads-half-its-source`.
   Le compte qui fait foi est celui de `make night-status`, qui lit les deux.

2. Run `make night-status` — the open rows in index order, the parked tasks, the working
   tree, and the roadmap discipline of the last 14 days (`make roadmap-discipline`, R197).
   (`.claude/dev-docs/work-in-progress/` is no longer used: it has been empty since the
   two-file roadmap; open work lives in the index only — R201.)

3. Read the last 5 entries from `DEVLOG.md` (repo root) — show title + "What changed" lines only, no full body.

4. Read `.claude/sessions/pending-rex.md` if it exists and list any un-promoted REX drafts
   (session cleanup reminder). (`_archived_retro.md` is frozen — no longer read, R201.)

5. `ls docs/adr/` — show the 2 ADRs most relevant to the open rows (match by id, technology keyword, or domain). Read only those two; show ADR number + title + the one-line `## Decision`. Skip if the index is empty.

6. Output a compact session brief in this format:

---
**Session Brief — YYYY-MM-DD**

**Open now** (`## 📋 Tâches ouvertes`, in index order, 5 lines max):
<Rnnn — task — P — critic: requis|non>

**Waiting on you** (`## 🙋 En attente de toi`):
<Rnnn — the gesture it awaits> (or "none")

**Roadmap discipline (14 d):** <the 3 lines of `make roadmap-discipline`>

**Deferred from last sessions:**
- <deferred action or Next session item>
(omit section if nothing deferred)

**Relevant ADRs:**
- ADR-XXX: <title> — <rationale>
(omit section if the index is empty)

**Last changes:**
- YYYY-MM-DD: <DEVLOG title>
- ...

**Suggested next action:**
<highest-priority unchecked item from checklist.md — the `## 📋 Tâches ouvertes` index is
ordered; prefer an item marked actionable over one marked BLOQUÉ or DIFFÉRÉ>
---

7. If both index tables are empty: say the roadmap is at 0 open task, and that the next action
   must first be written as an index row (R196) before any code.

## When to use

Run `/resume` as the very first command after any `/clear` or new session start when a feature was in progress.
Order: `/resume` first → then work. Not `/sprint` (that's for roadmap overview only).
