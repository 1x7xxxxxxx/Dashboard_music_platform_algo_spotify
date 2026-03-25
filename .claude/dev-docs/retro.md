# Retrospective Log

Auto-appended by `strategic-plan-architect` background agent after each session.
Format: `## YYYY-MM-DD HH:MM` + Changed / Why / Decisions / Status

---

## 2026-03-12 — Bricks 9–13, 16–17 + bug fixes

**Changed:**
- `src/utils/retry.py`, `src/utils/error_handler.py` (Brick 9)
- `tests/` directory — 4 test files, `conftest.py` (Brick 10)
- `src/utils/freshness_monitor.py` (Brick 11)
- `src/dashboard/utils/pdf_exporter.py`, `src/dashboard/views/export_pdf.py` (Brick 12)
- `src/dashboard/utils/csv_exporter.py`, `src/dashboard/views/export_csv.py` (Brick 13)
- `src/database/ml_schema.py`, `src/utils/ml_inference.py` (Brick 16)
- `airflow/dags/ml_scoring_daily.py`, `airflow/debug_dag/debug_ml_scoring.py` (Brick 16)
- `src/dashboard/views/trigger_algo.py`, `src/dashboard/views/ml_performance.py` (Brick 17)
- `scripts/create_missing_tables.sql` — 16 missing tables added

**Why:** Complete P2 (error handling, tests, monitoring) and P3 (exports, ML) bricks from the roadmap.

**Decisions:**
- XGBoost loaded directly from `.ubj` files (not mlflow runtime) — avoids mlflow server dependency
- WeasyPrint with graceful HTML fallback when PDF generation fails
- Tests mock DB connections via `conftest.py` fixtures — avoids live DB requirement for CI

**Status:** 15/17 bricks complete. P2 done. P3 done. Bricks 14–15 (FastAPI + Railway) outstanding.

**Blockers:** SoundCloud + Instagram credentials expired; `meta_campaigns` schema incomplete.

---

## 2026-03-12 — Session: Dashboard bug fixes + useful_links + airflow_kpi logs

**Changed:**
- `src/dashboard/utils/pdf_exporter.py` — fixed `WHERE is_active = TRUE` (column is `active`)
- `src/dashboard/utils/kpi_helpers.py` — fixed table references
- `src/dashboard/utils/csv_exporter.py` — fixed date columns
- `src/dashboard/views/useful_links.py` — new view (5 tabs, static links)
- `src/dashboard/views/airflow_kpi.py` — added "Logs par Run" tab
- `src/dashboard/views/home.py` — DAG status cards
- Multiple views — fixed `use_container_width` deprecation warning

**Why:** Post-test audit revealed 9 bugs across exporter utilities; useful_links and airflow log viewer requested by user.

**Decisions:** `scripts/create_missing_tables.sql` as a migration script (not re-running init_db.sql)

**Status:** ✅ Bugs fixed. Dashboard operational.

---

## 2026-03-23 — Configuration restructuring

**Changed:**
- `CLAUDE.md` — rewritten to ≤200 lines, English only, removed coding standards
- `.claude/hooks/session_summary.py` — added Step 4 (pytest runner), English comments
- `.claude/skills/` — created 4 skill files (dashboard-view, airflow-dag, db-schema, response-protocol)
- `.claude/agents/` — created 4 agent definitions (strategic-plan-architect, code-architecture-reviewer, build-error-resolver, web-research-specialist)
- `.claude/hooks/hook.md` — created hook documentation
- `.claude/commands/review-architecture.md`, `run-tests.md` — 2 new slash commands
- `.claude/scripts/run_tests.sh`, `check_env.py` — automation scripts
- `.claude/dev-docs/architecture.md`, `retro.md`, `roadmap/checklist.md` — created

**Why:** CLAUDE.md was 204 lines with French text and mixed concerns. Modular skills/agents/hooks structure enables progressive disclosure and avoids loading all context at once.

**Decisions:**
- Skills inject on keyword detection (reuse existing inject_context.py pattern)
- session_summary.py extended (not replaced) to preserve existing git/Docker logic
- CLAUDE_CODE_GUIDE.md archived (not deleted) — may contain patterns not yet fully migrated

**Status:** ✅ Restructuring complete. All hooks remain operational.
