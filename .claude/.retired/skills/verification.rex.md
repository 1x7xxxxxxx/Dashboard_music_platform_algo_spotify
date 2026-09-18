---
rex:
- date: 2026-05-31
  issue: Verification trigger referenced moving a brick to Completed in ROADMAP.md, a nonexistent file
    here
  fix: Repointed to checking off a brick as completed in .claude/dev-docs/roadmap/checklist.md
  severity: info
  ref: DEVLOG#2026-05-31
- date: 2026-08-21
  issue: 'Toutes les commandes de cette skill appartenaient à un AUTRE dépôt : `cd src/Application`, py_compile
    sur api.py/acquisition.py, curl sur /hmi/status, des seuils BINARY_FRAME_SIZE=3076 et « 27 features
    ». Aucun de ces chemins n''existe ici, et `cd src/Application` échoue assez discrètement pour ressembler
    à une phase sautée.'
  fix: Rewrote the four phases against this repo's real surfaces (ruff on the CI scope, pytest with the
    DB gate made explicit, the two DB-gated smokes, artist-preflight for tenant work). Kept the Iron Law
    and the forbidden-phrase table, which were portable. Also fixed the '## this project-Specific Checks'
    heading, a botched find/replace of 'MSDR-Specific'.
  ref: R36
  severity: warn
---

# Archive REX — skill `verification`

Historique migré depuis un sous-répertoire `.migrated/` (supprimé depuis) le 2026-09-17.
Il y vivait **hors du périmètre** de `validate_rex.py` : `_SCAN_DIRS` porte
`("skills", "*.md")`, un glob à UN niveau qui n'atteint pas `.migrated/`.
Ces 1 leçons n'étaient ni validées, ni comptées, ni lisibles par
aucun outil — et le mécanisme de remplacement annoncé par
`validate_rex.py:160-172` (« a colocated `<name>.rex.md` archive ») n'avait
jamais été créé : `find .claude -name '*.rex.md'` rendait vide.

⚠️ `keywords:` a été RETIRÉ du frontmatter : une archive n'est pas un outil
injectable, et `_iter_tools` l'exclut explicitement du dénominateur.

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
| "Tests pass" / "All tests pass" | Run the project test command → paste full output |
| "Fixed" / "The bug is fixed" | Run the originally failing test, show it now passes |
| "Done" / "Brick complete" | Run Phase 1+2 minimum below |
| "It works" / "Should work now" | Run the relevant smoke test, paste output |
| "Clean" / "No issues" | Run the project linter (`ruff`, `eslint`, `golangci-lint`, ...) → paste output |

**Blocked words without evidence:** "should work", "probably fine", "seems good", "I think it passes"

**Never claim "passes" based on a prior run from a different session.**

---

## 4-Phase Verification Gate

Run after every feature completion, before declaring a brick done, before any deployable artifact build.

### When to Use

- After modifying any module that other code depends on
- Before checking off a brick as completed in `.claude/dev-docs/roadmap/checklist.md`
- After a schema change / migration
- Before `docker compose build` / `docker buildx` / any deploy

### Phase 1 — Syntax & Lint

```bash
# Adapt to your project's linter:
# Python:    ruff check . --select E9,F
# JS/TS:     npx eslint . --max-warnings 0
# Go:        golangci-lint run
# Rust:      cargo check
```

**STOP if any blocking lint error. Fix before continuing.**

### Phase 2 — Test Suite

```bash
# Adapt to your project's test runner:
# Python:  python3 -m pytest tests/ -v --tb=short
# JS/TS:   npm test
# Go:      go test ./...
# Rust:    cargo test
```

Report actual numbers: Total / Passed / Failed. **Never copy from a prior session — run it now.**

**STOP if any test fails. Fix before Phase 3.**

### Phase 3 — Smoke Test

Run the project's smoke check — typically a curl against a `/healthz` endpoint, a CLI invocation that exercises the happy path, or a single end-to-end scenario. Examples:

```bash
# HTTP service
curl -fsS http://localhost:<port>/healthz

# CLI tool
./bin/<your-cli> --version && ./bin/<your-cli> <example-command>

# Worker / pipeline
<your-trigger-command> && <your-verify-command>
```

Check for: no error in output, exit code 0, expected payload shape.

### Phase 4 — Build / Container Sanity

```bash
# Adapt:
# docker compose build --no-cache <service>
# docker buildx build --platform linux/amd64 .
# npm run build
# cargo build --release
```

Run only if dependencies / Dockerfile / build config changed.

## Output Format

```
VERIFICATION REPORT
===================
Phase 1 — Lint:    [PASS/FAIL] (X issues)
Phase 2 — Tests:   [PASS/FAIL] (X/Y passed)
Phase 3 — Smoke:   [PASS/FAIL]
Phase 4 — Build:   [PASS/SKIP/FAIL]

Overall: [READY / NOT READY]
```

## Project-specific checks

(Populate this section in your project's own l'ancien fichier plat `verification` after bootstrap. Examples:)

- `<critical-file>.<ext>` modified: verify <invariant> still holds (e.g. constant value, test count, schema version)
- Schema migration added: verify forward roundtrip on a scratch DB
- Build artifact size grew > X%: investigate which dependency was added
- New external integration: verify auth credential rotation procedure documented

## Exceptions (must be stated explicitly)

- Hardware not connected: "<device> not connected — cannot run smoke test"
- Service not running: "service not started — ran lint+tests only"
- Build > 5 min: run Phase 1+2 only, note the skip
- External API unreachable: "<API> 5xx — local logic verified, retry pending"
