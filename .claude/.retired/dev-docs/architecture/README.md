# Retired 2026-08-21 — roadmap item R34

This directory was a **second** architecture surface, inherited from the baseline
payload. The populated one is `.claude/dev-docs/architecture.md`, which CLAUDE.md,
`/review-architecture` and the `response-protocol` skill all name.

Why it was retired rather than filled — four measurements, not a preference:

1. **584 `[TODO]` markers over 1301 lines.** `database_schema.md` alone carried 539.
2. **No consumer.** The only live reference was `agents/code-architecture-reviewer.md`,
   an agent that CLAUDE.md itself flags as never invoked (named in a table, and a
   tool named in a table is invoked 0 times out of 23 measured).
3. **The mechanism that would fill it does not exist here.** The files instruct
   "run `generate-dev-docs.py` then `/dev-docs-init` to let the dev-docs-architect
   agent fill the rest". There is no `/dev-docs-init` command and no
   `dev-docs-architect` agent in this repo, and the generator's default
   `--src-dir` is `src/Application`, another repo's layout. It is wired to no
   Makefile target and no hook.
4. **A hand-maintained schema copy is a drift generator.** The authoritative
   schema sources are `migrations/*.sql`, `src/database/*_schema.py`, and
   `make schema-check`, which compares against the live database by definition.
   The `api-router-schema-drift` class in `error-classes.md` is what happens when
   a second copy is trusted.

`GANTT.md` and `BRICKS.md` were retired earlier for the same reason — an
unadapted stub that names a workflow the repo does not have.

To regenerate any of this on demand:
`python3 tools/generate-dev-docs.py --project-dir . --src-dir src`
