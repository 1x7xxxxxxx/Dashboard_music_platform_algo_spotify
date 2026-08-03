---
name: verification
description: Blocks completion claims that have no fresh command output behind them. Use before saying tests pass, it works, fixed, done, or ready, and after any non-trivial change. It checks that evidence exists — it does not write tests and does not judge whether the evidence is sufficient design-wise. Assumes commands can actually be executed in this environment.
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
| "Tests pass" / "All tests pass" | `cd src/Application && python3 -m pytest tests/ -q --tb=short` → paste full output |
| "Fixed" / "The bug is fixed" | Run the originally failing test, show it now passes |
| "Done" / "Brick complete" | Run Phase 1+2 minimum below |
| "It works" / "Should work now" | Run the relevant smoke test, paste output |
| "Clean" / "No issues" | `ruff check <module path> --select E9,F` → paste output |

**Blocked words without evidence:** "should work", "probably fine", "seems good", "I think it passes"

**Never claim "passes" based on a prior run from a different session.**

---

## 4-Phase Verification Gate

Run after every feature completion, before declaring a brick done, before any Docker deploy.

### When to Use

- After modifying `api.py`, `database.py`, `acquisition.py`, `background_ml.py`, `features.py`
- Before rotating a brick from `roadmap/checklist.md` (actif) into `roadmap/archive.md`
- After any Alembic revision (new migration in `<module path>`)
- Before `docker compose build`

### Phase 1 — Syntax & Lint

```bash
cd src/Application
ruff check . --select E9,F 2>&1 | head -30
python3 -m py_compile api.py database.py acquisition.py features.py background_ml.py 2>&1
```

**STOP if any E9 (syntax error). Fix before continuing.**

### Phase 2 — Test Suite

```bash
cd src/Application
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Report actual numbers: Total / Passed / Failed. **Never copy from a prior session — run it now.**

**STOP if any test fails. Fix before Phase 3.**

### Phase 3 — API Smoke Test

```bash
# Requires uvicorn running: uvicorn api:app --reload
curl -s http://localhost:8000/data/latest | python3 -m json.tool | head -20
curl -s http://localhost:8000/health-score | python3 -m json.tool
curl -s http://localhost:8000/hmi/status | python3 -m json.tool
```

Check for: no 500 errors, no 503 (XGBoost bundle missing), valid JSON, `machine_state` present.

### Phase 4 — Docker Build Sanity

```bash
cd /mnt/c/Users/timot/Desktop/msdr_predictive_maintenance
docker compose build --no-cache api 2>&1 | tail -20
```

Run only if `requirements.txt` or `Dockerfile` changed.

## Output Format

```
VERIFICATION REPORT
==========================
Phase 1 — Lint:    [PASS/FAIL] (X issues)
Phase 2 — Tests:   [PASS/FAIL] (X/Y passed)
Phase 3 — API:     [PASS/FAIL] (/data/latest, /health-score, /hmi/status)
Phase 4 — Docker:  [PASS/SKIP/FAIL]

Overall: [READY / NOT READY]
```

## this project-Specific Checks

- `database.py` modified: verify `initialize_db()` runs without error on fresh DB
- `api.py` modified: verify no duplicate routes (`grep "^@app\." api.py | sort | uniq -d`)
- `features.py` modified: verify 27 features still extracted
- `acquisition.py` modified: verify `BINARY_FRAME_SIZE=3076` and `NUM_FLOATS=768` unchanged

## Exceptions (must be stated explicitly)

- Hardware not connected: "USB CDC not connected — cannot run acquisition smoke test"
- Service not running: "uvicorn not started — ran lint+tests only"
- Build > 5 min: run Phase 1+2 only, note the skip
