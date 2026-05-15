---
globs: ["Makefile"]
rex:
  - date: 2026-05-15
    issue: "`make dashboard` ran Streamlit then crashed mid-render: Postgres 5433 down, failed late with no actionable message"
    fix: "Added Cross-Cutting Rule #10 + this spec; `dashboard: check-env` is the precedent prerequisite; error class make-fail-late catalogued"
    severity: warn
    ref: "DEVLOG#2026-05-15"
---

# Rule: Makefile fail-fast

Mirror of CLAUDE.md Cross-Cutting Rule #10. Auto-injected when the `Makefile`
is touched.

## The rule

Any target that invokes a **runtime dependency** MUST declare a prerequisite
that validates it and fails fast with a message naming the fix command.

Runtime dependencies in this repo:

| Dependency | Symptom if missing | Fix command |
|---|---|---|
| Docker / `docker-compose` | `Cannot connect to the Docker daemon` | `docker-compose up -d` |
| Live Postgres (`localhost:5433`) | `connection refused` mid-render | `make up` |
| venv interpreter (`venv/Scripts/python.exe`) | `No such file` | `make sync` |
| `uv` | `uv: command not found` | `pip install uv` |
| `streamlit` / dashboard deps | `ModuleNotFoundError` | `make sync` |

The precedent is `check-env` (`Makefile`), used as `dashboard: check-env`. It
checks dashboard imports, pip coherence, and Postgres reachability, exiting 1
with `❌ … Run: make up` *before* `streamlit run`.

## Exempt

File-only targets that touch nothing at runtime: `help`, `clean`,
`graph-html`, `graph-update`. An inline guard inside the recipe (e.g. `migrate`
checks `PG_CONT` then `exit 1`) is an accepted variant of a prerequisite.

## Severity

A runtime target with no precondition and no actionable failure message is a
**P3 (UX)** bug — never P1; do not fix it during a P1 session.

## Detection (error class `make-fail-late`)

Heuristic signature (report-only, manual triage — see
`.claude/dev-docs/error-classes.md`):

```bash
! grep -nE "^\t.*(docker|streamlit|psql|uv )" Makefile | grep -vE "check-env|check-manifest"
```

## First sweep — 2026-05-15

| Target | Runtime dep | Has precondition? | Disposition |
|---|---|---|---|
| `dashboard` | streamlit + Postgres | ✅ `check-env` | OK |
| `check-manifest` | python3 only (stdlib) | n/a | OK |
| `migrate` | Postgres (`PG_CONT`) | ✅ inline guard (accepted variant) | OK |
| `up` / `down` / `logs` | Docker | ❌ none | **P3 — reported**, not auto-rewritten (never rewrite unrelated code unasked) |
| `test` | venv `pytest` | ❌ none | **P3 — reported** |

Reported items are intentionally left for a dedicated, reviewed change — they
are out of scope of the rule's introduction.
