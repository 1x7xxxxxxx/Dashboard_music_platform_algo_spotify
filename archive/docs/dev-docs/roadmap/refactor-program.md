# Sequenced refactor program

> Execution tracker for the dashboard refactor backlog. The **detailed
> per-item spec** (structure dumps, target layouts) lives in
> `.claude/dev-docs/refactor-audit-dashboard.md` — this file is the ordered
> work queue + the definition-of-done, not a duplicate of the audit.
>
> Created 2026-05-15. Resume with: *"Read
> `.claude/dev-docs/roadmap/refactor-program.md` and pick the next
> non-DONE item whose trigger has fired."*

## Why this exists

`credentials.py` (892 l) prompted a "refactor everything" request. A blanket
multi-file rewrite is explicitly rejected (see Guardrails). Instead: a
prioritised queue, one file per PR, each gated by a *trigger* so we refactor
files we're about to touch anyway (cheap) and never gold-plate stable code.

## The queue

| # | Item | Effort | Risk | ROI | Trigger | Status |
|---|---|---|---|---|---|---|
| R1 | `credentials.py` → package (audit #3) | 3–4 h | Mod | Moy | fired (token-auth work) | ✅ **DONE 2026-05-15** (`acf8b6f`) |
| R2 | `kpi_helpers.py` ruff cleanup (audit #4) | 30 m | Faible | Faible | any time (quick win) | ✅ **DONE 2026-06-01** (already clean) |
| R3 | `view_session()`/`project_db()` adoption (audit #2) | ~1.5 h | Faible | Moy | per-view, opt-in | ⏳ partial — see note |
| R4 | `trigger_algo.py` (1209 l) → package (audit #1) | 4–6 h | Mod | **High** | next edit to that view | ✅ **DONE 2026-06-01** (file had grown to 2279 l / 6 tabs) |
| R5 | `pdf_exporter.py` (856 l) → `_render_section()` (audit #5) | 2–3 h | Faible | Moy | next PDF feature | ✅ **DONE 2026-06-01** (primitives, not mega-helper) |
| R6 | `revenue_forecast.py` (608 l) calc/UI split (audit #6) | 2 h | Faible | Moy | when forecast accuracy questioned | ✅ **DONE 2026-06-01** (core math + loaders, +8 tests) |

**R3 note:** the helper already ships (`src/dashboard/utils/__init__.py`
`view_session`/`project_db`); the remaining work = migrating the ~30
un-migrated views. That backlog is already tracked as the
**`view-session-adoption`** open error-class in
`.claude/dev-docs/error-classes.md` — do **not** duplicate or re-plan it
here; R3 is a pointer, migration stays opt-in per view (migrating changes
behaviour, deliberately incremental, NOT CI-blocking).

Recommended order when triggers are equal: **R2** (free), then **R4** (highest
ROI, the 1209-line file is the most hostile to edit), then R5, R6. R3 trickles
alongside whatever view you're already in.

## Guardrails (binding — from audit "Explicitly NOT recommended")

- **No big-bang** "tout casser tout reconstruire" — no UI test net; it breaks
  every in-flight branch.
- **No FastAPI/React migration** — changes the product, out of scope.
- **No service/repository/domain layers** — rejected by `docs/adr/ADR-002`.
  Refactors stay within existing patterns.
- **Never split a view < 400 lines** — over-fragmentation costs more than the
  monolith (median view ~250 l is fine).
- **One file per PR.** Mixing two refactors in one PR forfeits the "revert one
  thing" safety.
- **Trigger discipline:** prefer "wait until you next touch this file".
  Refactoring a file you're about to edit is cheap; refactoring a stable file
  you don't otherwise touch is gold-plating.

## Definition of done (per item)

1. Pure relocation — **zero behaviour change** unless the item explicitly is
   a behaviour change (none here are). Diff is move-only + import rewiring.
2. `ruff check src/ tests/` clean.
3. `pytest tests/ -q` pass count **unchanged** (these refactors touch no
   tested public surface; a moved count means something leaked).
4. Import smoke: the view's public entry (`from views.<name> import show`)
   still resolves; no circular import.
5. Manual Streamlit smoke of every touched view (no automated UI net) —
   render + one interaction per tab.
6. `refactor-audit-dashboard.md` item marked ✅ DONE + as-built layout if it
   deviates from the sketch (state the deviation + why; Rule #2).
7. This file's queue row → ✅ DONE + commit SHA.
8. One logical commit through the pre-commit chain (`--no-verify` is blocked
   by `guard_destructive.py`); plain `git push` (never `-f`).

## History

- 2026-05-15: program created. R1 completed same session (`acf8b6f`) — the
  token-auth alignment work fired its trigger. R3 reconciled with the
  existing `view-session-adoption` error-class (no duplication).
