# ADR-001 — Roadmap multi-files conserved (deviation from baseline)

- **Status:** Accepted
- **Date:** 2026-05-14
- **Deciders:** @1x7xxxxxxx

## Context

The baseline Claude Code template (`setup-claude-code.sh` v2026.05.11) installs a single `.claude/dev-docs/ROADMAP.md` as the canonical roadmap tracker (P1/P2/P3/P4 sections). The project pre-dates this baseline and uses a multi-file roadmap layout under `.claude/dev-docs/roadmap/` whose entry point is `checklist.md` (~243 lines, 17 completed bricks + open P1/P2/P3/P4 sections + a "Live user counter" P3 section just added in Brick 32).

After `--update` merge on 2026-05-14, both layouts cohabit on disk:
- `.claude/dev-docs/roadmap/checklist.md` — project's existing canonical tracker
- `.claude/dev-docs/ROADMAP.md` — new baseline template (mostly empty)

The decision was whether to migrate content from `roadmap/checklist.md` into the new `ROADMAP.md` (single-file baseline convention) or keep the multi-file layout.

## Decision

Keep `.claude/dev-docs/roadmap/checklist.md` as the project's canonical roadmap. The baseline `.claude/dev-docs/ROADMAP.md` is treated as an inert template artifact (not the active tracker) and may be deleted in a future cleanup.

## Consequences

### Positive
- Zero migration work: no risk of dropping a brick, an open bug, or a completed-checkmark during a copy.
- Existing slash commands and hooks that reference `roadmap/checklist.md` keep working unchanged.
- The session-resume prompt baked into `checklist.md` (`"Read .claude/dev-docs/roadmap/checklist.md and continue with the next unchecked item."`) remains the anchor for `/clear` recovery.

### Negative / Trade-offs
- Deviation from the baseline template convention — anyone applying the baseline elsewhere expects a single `ROADMAP.md`.
- `check_roadmap_update.py` baseline hook may surface a reminder against `ROADMAP.md` rather than `roadmap/checklist.md`. If that proves noisy, override the hook's target or supersede this ADR.

### Neutral / Operational
- The `ROADMAP.md` template file at the dev-docs root is harmless (a stub). Either leave it as documentation of the baseline convention or delete it in a follow-up sweep.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Migrate `roadmap/checklist.md` content into `ROADMAP.md` | High risk of accidental brick loss during reformat; no functional gain; would force a sweep of all references in commands/skills/hooks. |
| Keep both as parallel trackers | Splits the source of truth, creates drift, contradicts the "single canonical tracker" rule from the baseline anyway. |
| Delete `ROADMAP.md` baseline stub immediately | Cosmetic; defer to a future cleanup ADR if the stub becomes a source of confusion. |
