---
globs: ["**/*.py"]
rex: []
---

# Python conventions — {{PROJECT_NAME}}

- Follow PEP8; ruff (E, F, W) is the linter — no manual style overrides
- Type hints required on all function signatures (args + return type)
- No bare `except:` — always catch a specific exception class
- No f-strings in SQL queries — parameterized queries only (`?` placeholders)
- Max function length: 40 lines. Extract helpers if exceeded.
- No mutable default arguments (`def f(x=[])` → `def f(x=None)`)
- Imports: stdlib → third-party → local, one blank line between groups
- Docstrings: one short line max, only when the purpose is non-obvious from the name
- Timestamps written to DB or returned from API handlers must be UTC-aware: `datetime.now(timezone.utc).isoformat(timespec="milliseconds")`. Bare `datetime.now()` is forbidden outside purely cosmetic contexts (email body strftime, PDF header, filename suffix) that never persist. Rationale: brick `sync-phase-0-clock-hygiene` — bare `datetime.now()` is host-TZ-naïf, breaks `fetch_plc_context_at` ±500ms window on non-UTC containers, and produces ambiguous strings that silently mis-order vs aware `+00:00` siblings under lexicographic comparison.
