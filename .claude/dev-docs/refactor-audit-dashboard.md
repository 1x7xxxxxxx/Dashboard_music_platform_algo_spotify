# Refactor audit — `src/dashboard/`

> **Status** : audit only — no code refactor in this commit. Read this, decide
> per item, then schedule the ones you want as separate bricks. Each item below
> ships with concrete entry points so you can scope precisely.

## Scope

`src/dashboard/views/` totals **14 257 lines across 33 files**, plus 5 utils
files. The dashboard is the most touched part of the project (every brick that
adds a feature also touches a view), so reducing friction here pays back across
all future work.

## Headline numbers

| Metric | Value |
|---|---|
| Total view files | 33 |
| Total view lines | 14 257 |
| Median view size | ~250 lines |
| 95th-percentile view | 608 lines |
| Largest view | 1 209 lines (`trigger_algo.py`) |
| Largest util | 861 lines (`pdf_exporter.py`) |
| Files manually opening a DB connection | 34 |
| Files manually closing in `finally` | 31 |

## Prioritized pain points

### #1 — `views/trigger_algo.py` (1 209 lines) — split into a package

**Structure today** (read from the file with `grep ^def`) :
```
_display_prob_bar        @ 69
_show_ml_section         @ 81
_show_heuristic_section  @ 90
_show_key_factors        @ 111
_load_ml_pred            @ 156
_load_xgb_model          @ 191
_compute_score_20        @ 204
_show_tab_global         @ 218   (~240 lines)
_show_tab_algos          @ 459   (~155 lines)
_show_tab_budget_roi     @ 614   (~264 lines)
_show_tab_explainability @ 878   (~ 73 lines)
_show_tab_model          @ 951   (~115 lines)
show                     @ 1067  (~140 lines, top-level router)
```
Five logical tabs already factored into `_show_tab_*` helpers — the split is
*pre-done* by the original author. We just need to move them to files.

**Target layout** :
```
src/dashboard/views/trigger_algo/
  __init__.py            # exports show()
  _common.py             # _display_prob_bar, _load_ml_pred, _load_xgb_model, _compute_score_20
  _tab_global.py         # _show_tab_global + dependencies
  _tab_algos.py          # _show_tab_algos
  _tab_budget_roi.py     # _show_tab_budget_roi
  _tab_explainability.py # _show_tab_explainability
  _tab_model.py          # _show_tab_model
  router.py              # the slim show() function (~50 lines)
```

| Property | Value |
|---|---|
| Effort | 4–6 h |
| Risk | Modéré — no UI tests; ruff + pytest must remain green; manual smoke-test the 5 tabs |
| ROI | **High** — most-used admin view; current 1 209-line file is hostile to edit |
| Trigger | Next time you need to touch any tab in this view |

---

### #2 — Context manager `with project_db() as db:` — kill the boilerplate

**Today** : 34 view files contain `db = get_db_connection()` + `try/finally:
db.close()`. That's ~5 lines of boilerplate × 34 files = ~170 lines that could
be collapsed.

**Target** : add a `@contextmanager` helper in `src/dashboard/utils/__init__.py`
or a new `src/dashboard/utils/db.py` :

```python
from contextlib import contextmanager

@contextmanager
def project_db():
    db = get_db_connection()
    if db is None:
        raise RuntimeError("Database unreachable; Docker not up?")
    try:
        yield db
    finally:
        db.close()
```

Each view then becomes :
```python
def show():
    with project_db() as db:
        # ... body
```

| Property | Value |
|---|---|
| Effort | 1–1.5 h (mechanical, find/replace + small adjustments) |
| Risk | **Faible** — single-line change per file; revert by undoing 34 edits |
| ROI | Moderate — every future view shrinks by 5 lines and skips a class of `db.close()` bugs |
| Trigger | Anytime you want a 1-hour quick win |

---

### #3 — `views/credentials.py` (853 lines) — split by platform ✅ DONE 2026-05-15

> **Status: completed** (commit on `main`, 2026-05-15). The 893-line file is
> now the package `src/dashboard/views/credentials/`. **As-built layout**
> (deviates from the sketch below — `_registry.py` + `_render.py` added so
> `router.py` is genuinely slim ~100 l instead of ~400 l; no cross-cutting
> rule mandated the literal file list):
> ```
> credentials/
>   __init__.py            # re-exports show()
>   _core.py               # Fernet crypto + DB load/save + Airflow-state + consts
>   _platform_spotify.py   # _test_spotify + _guide_spotify
>   _platform_youtube.py   # _test_youtube + _guide_youtube
>   _platform_soundcloud.py# _test_soundcloud + _guide_soundcloud
>   _platform_meta.py      # _test_meta + _guide_meta
>   _registry.py           # PLATFORMS + CONNECTION_TESTS + guide dispatch
>   _render.py             # Streamlit render/form helpers + _handle_save
>   router.py              # slim show()
> ```
> Pure cut/paste, zero logic change. Verified: ruff clean, pytest 237 passed,
> import smoke resolves `from views.credentials import show`, blast radius
> zero (only `app.py:324` imports it). The original sketch is kept below for
> historical context.

**Structure today** :
- Core helpers : `_get_fernet`, `_encrypt_secrets`, `_decrypt_secrets`, `_mask`, `_fetch_dag_last_states`, `_load_credentials`, `_save_credentials`, `_decode_row`
- Per-platform test functions : `_test_spotify`, `_test_youtube`, `_test_soundcloud`, `_test_meta`
- Per-platform guide functions : `_guide_spotify`, `_guide_youtube`, `_guide_soundcloud`, `_guide_meta`
- Top-level `show` + `_render_platform_guide` + `_render_global_kpi`

**Target layout** :
```
src/dashboard/views/credentials/
  __init__.py
  _core.py          # encrypt/decrypt/mask + load/save/dag-states
  _platform_spotify.py
  _platform_youtube.py
  _platform_soundcloud.py
  _platform_meta.py
  router.py         # slim show() + platform dispatch
```

| Property | Value |
|---|---|
| Effort | 3–4 h |
| Risk | Modéré — critical onboarding path; encryption code is sensitive |
| ROI | Moyen — file is rarely modified post-onboarding stabilization |
| Trigger | Next time you add a credentials-related feature OR a new platform |

---

### #4 — `utils/kpi_helpers.py` (418 lines + 7 ruff findings) — lint cleanup

**Issues** (from `rtk proxy ruff check`) :
- `F401` : unused imports (`date` at line 2, likely others)
- `F541` : f-strings with no placeholders (multiple SQL queries that should be plain strings)
- `F841` : unused variables (`delta_color` in `home.py`, but the file has its own findings)

**Target** : ruff `--fix` then manual review. Should resolve in ≤ 30 minutes
without touching behavior.

| Property | Value |
|---|---|
| Effort | 30 min |
| Risk | Faible — pure lint, no behavior change |
| ROI | Faible — cosmetic but unblocks future `ruff check src/` from being noise |
| Trigger | Any time |

---

### #5 — `utils/pdf_exporter.py` (861 lines) — template-based render

**Today** : repeats a `_collect_<platform>(...)` + `_render_<platform>(...)`
pattern for ~6 platforms. The render code is structurally similar across
platforms (header + KPIs + table + footer).

**Target** : extract a `_render_section(title, kpis, table_data)` generic helper.
Replace ~6 `_render_*` with calls to it. Estimated reduction : ~300 lines.

| Property | Value |
|---|---|
| Effort | 2–3 h |
| Risk | Faible — pure layout change, easy to compare PDF byte-by-byte against a baseline |
| ROI | Moyen — touched ponctuellement (Brick 12 PDF export) |
| Trigger | Next PDF feature change |

---

### #6 — `views/revenue_forecast.py` (608 lines) — split calc / UI

**Today** : forecasting math (Prophet ? linear regression ?) interleaved with
Streamlit rendering.

**Target** : move math to `src/dashboard/utils/revenue_forecast.py`. View calls
the util and renders the result.

| Property | Value |
|---|---|
| Effort | 2 h |
| Risk | Faible — math is deterministic, can be tested standalone |
| ROI | Moyen — also unlocks easier unit tests for the forecast logic |
| Trigger | Next time forecasting accuracy is questioned |

---

### #7 — `views/home.py` (430 lines) — surveillance, no refactor yet

Eight `_section_*` helpers already factored. Brick 32 added
`_section_live_pulse` (≈ 10 lines). Acceptable as long as it stays under 500.
If the next brick adds another section, then refactor into `home/_sections.py`.

| Property | Value |
|---|---|
| Effort | 0 today |
| Risk | n/a |
| ROI | n/a |
| Trigger | When line count crosses 500 |

---

## Suggested attack sequence

If you want to **start somewhere** without overcommitting, follow this order :

| Rank | Item | Effort | Risk | ROI | Quick-win flag |
|---|---|---|---|---|---|
| 1 | #2 context manager `project_db()` | 1–1.5 h | Faible | Moderate | ✅ quick win — touches 34 files but each change is 1 line |
| 2 | #4 ruff cleanup on `kpi_helpers.py` | 30 min | Faible | Faible | ✅ quick win — pure lint |
| 3 | #1 `trigger_algo.py` package split | 4–6 h | Modéré | High | Wait for the next feature on that view |
| 4 | #3 `credentials.py` split | 3–4 h | Modéré | Moyen | ✅ DONE 2026-05-15 |
| 5 | #5 `pdf_exporter.py` template | 2–3 h | Faible | Moyen | Wait until next PDF feature |

The "wait" trigger matters : refactoring a file you're about to modify is cheap
(you're already paging it in). Refactoring a stable file you don't otherwise
touch is gold-plating.

## Explicitly NOT recommended

- **"Tout casser tout reconstruire"** — high risk, no UI test safety net, breaks every in-flight branch.
- **Migration to FastAPI + React** — changes the product (no longer Streamlit), out of scope.
- **Introducing service/repository/domain layers** — explicitly rejected by `docs/adr/ADR-002`. The refactors above stay within the existing patterns.
- **Splitting view files smaller than 400 lines** — over-fragmentation hurts more than it helps; the median 250-line view is fine.

## Quick reproduction commands

```bash
wc -l src/dashboard/views/*.py | sort -n | tail -10        # top offenders
grep -rln "db = get_db_connection" src/dashboard/views/ | wc -l   # boilerplate counter
ruff check src/dashboard/utils/kpi_helpers.py             # see findings #4
```
