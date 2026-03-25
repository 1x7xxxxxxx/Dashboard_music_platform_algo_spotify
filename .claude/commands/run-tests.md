# Run Tests

Execute the full pytest suite and analyze failures.

## Command

```bash
python3 -m pytest tests/ -v --tb=short 2>&1
```

## Analysis Protocol

1. For each `FAILED` test: identify the **source file** (not the test file) from the stack trace
2. For each `ERROR`: check if it is an import error → likely a missing dependency or broken `src/` path
3. Do NOT re-run tests without applying a fix first
4. If ≥5 failures: spawn the `build-error-resolver` agent (see `.claude/agents/build-error-resolver.md`)

## Output Format

```
[FAIL] tests/test_<name>.py::test_<case>
  Root file: src/path/to/file.py:line
  Root cause: [1 sentence — the actual bug]
  Fix: [specific change to apply]

[ERROR] tests/test_<name>.py — ImportError: [module]
  Root cause: [missing dependency or sys.path issue]
  Fix: [specific command or code change]

Summary: N passed, N failed, N errors
```

## Common Failure Patterns

| Symptom | Likely cause | Fix location |
|---|---|---|
| `psycopg2.OperationalError` | Test DB not running or wrong config | `.env.local` or `config.yaml` |
| `ImportError: src.collectors.*` | Missing `sys.path.insert` | Top of the file being tested |
| `KeyError: 'artist_id'` | Missing session_state mock in test | `tests/conftest.py` |
| `AssertionError: 0 != N` | Empty DataFrame returned | Check DB fixture or SQL filter |
