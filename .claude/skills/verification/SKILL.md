---
name: verification
description: Blocks completion claims that have no fresh command output behind them. Use before saying tests pass, it works, fixed, done, or ready, and after any non-trivial change. It checks that evidence exists — it does not write tests and does not judge whether the evidence is sufficient design-wise. Assumes commands can actually be executed in this environment.
rex:
  - date: 2026-08-21
    issue: "Every command in this skill belonged to another repo: `cd src/Application`, py_compile on api.py/database.py/acquisition.py/features.py/background_ml.py, curl on /hmi/status, a `cd` into /mnt/c/.../msdr_predictive_maintenance, and checks on BINARY_FRAME_SIZE=3076 and '27 features'. None of those paths exist here. A skill that is loadable by the model taught a verification procedure that cannot run — and 'cd src/Application' fails silently enough to look like a skipped phase."
    fix: "Rewrote the four phases against this repo's real surfaces (ruff on the CI scope, pytest with the DB gate made explicit, the two DB-gated smokes, artist-preflight for tenant work). Kept the Iron Law and the forbidden-phrase table, which were portable. Also fixed the '## this project-Specific Checks' heading, a botched find/replace of 'MSDR-Specific'."
    ref: "R36"
    severity: warn
---

# Verification

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

Before saying "tests pass", "it works", "fixed", "done", "ready" — run the command and paste the output.

## Forbidden Phrases (without evidence)

| Claim | Required evidence |
|-------|------------------|
| "Tests pass" / "All tests pass" | `python3 -m pytest tests/ -q` → paste the tail, **including the skip count** |
| "Fixed" / "The bug is fixed" | Run the originally failing test, show it now passes |
| "Done" / "Brick complete" | Phases 1+2 minimum, below |
| "It works" / "Should work now" | Run the relevant smoke, paste output |
| "Clean" / "No issues" | `ruff check src/ tests/` → paste output |

**Blocked words without evidence:** "should work", "probably fine", "seems good", "I think it passes"

**Never claim "passes" based on a prior run from a different session.**

---

## 4-Phase Verification Gate

Run after every feature completion, before rotating a brick, before any Docker deploy.

### When to Use

- After modifying anything under `src/collectors/`, `src/database/`, `src/dashboard/views/`, or `airflow/dags/`
- Before rotating a brick from `roadmap/checklist.md` (actif) into `roadmap/archive.md`
- After adding a file under `migrations/`
- Before `docker compose build`

### Phase 1 — Lint

```bash
ruff check src/ tests/
```

That scope is the authoritative one: it is exactly what CI blocks on. Widening it
to `tools/` or `.claude/scripts/` reports pre-existing findings CI does not gate
on — say so rather than presenting them as a regression.

**STOP on any E9 (syntax error).**

### Phase 2 — Test Suite

Pick the set first (cross-cutting rule #16 — it returns the whole suite when it
cannot conclude):

```bash
python3 .claude/scripts/select_tests.py
python3 -m pytest tests/ -q
```

Report Total / Passed / **Skipped** / Failed. The skip count is not noise here:
roughly 128 tests are DB-gated (`tests/db_gate.py`) and skip silently with no
Postgres on `localhost:5433`. "698 passed" with Postgres down is a **weaker**
claim than the same number with it up — state which one you ran.

**STOP if any test fails. Fix before Phase 3.**

### Phase 3 — The surfaces that mocks do not cover

Both are DB-gated. They exist because two production 500s (`/kpis`,
`/youtube/videos`) passed a fully mocked test suite:

```bash
make up                                            # Postgres must be reachable
python3 -m pytest tests/test_views_render_smoke.py -q   # the 39 Streamlit views
python3 -m pytest tests/test_api_db_smoke.py -q         # every data endpoint vs the real schema
```

Touched anything tenant-scoped (a collector, a DAG, an upsert payload, a
credential read)? Add:

```bash
make artist-preflight
python3 .claude/scripts/audit_tenant_writes.py
python3 tools/tenant_contamination_check.py
```

### Phase 4 — Docker Build Sanity

```bash
docker compose build --no-cache dashboard 2>&1 | tail -20
```

Run only if `requirements.txt`, `pyproject.toml` or a `Dockerfile` changed.
`src/` and `airflow/dags/` are volume-mounted — a code change there needs no rebuild.

## Output Format

```
VERIFICATION REPORT
==========================
Phase 1 — Lint:     [PASS/FAIL] (X issues, scope src/ tests/)
Phase 2 — Tests:    [PASS/FAIL] (X passed / Y skipped / Z failed, Postgres UP|DOWN)
Phase 3 — Smokes:   [PASS/SKIP/FAIL] (views, api, tenant)
Phase 4 — Docker:   [PASS/SKIP/FAIL]

Overall: [READY / NOT READY]
```

## Repo-specific checks

- A `migrations/*.sql` added → `make schema-check`, and confirm the migration is
  not ahead of its code (class `migration-ahead-of-its-code`: migration 065
  applied before its deploy broke YouTube collection in minutes).
- A view added → it must appear in `_NAV_SECTIONS` (`src/dashboard/app.py`) and
  render under `test_views_render_smoke.py`.
- A collector touched → `/audit-collectors`; every `except Exception` must `raise`
  (cross-cutting rule #6).
- Any query on `s4a_song_timeline` → carries `AND song NOT ILIKE '%1x7xxxxxxx%'`.

## Exceptions (must be stated explicitly)

- Postgres down: "Postgres unreachable on 5433 — 128 DB-gated tests skipped, ran lint+unit only"
- Docker unavailable: "Docker daemon not reachable — Phase 4 skipped"
- Build > 5 min: run Phases 1+2 only, note the skip
