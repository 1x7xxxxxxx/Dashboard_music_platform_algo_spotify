# Review Architecture

Audit the Mermaid diagrams in `.claude/dev-docs/architecture.md` against the current codebase state.

## Steps

1. Read `.claude/dev-docs/architecture.md` (current diagrams)
2. Run `git status --short` to identify recently modified files
3. For each modified file, verify its node and edges are still accurate in the diagrams
4. Check that all new views are registered in `app.py` routing
5. Check that all new DAGs have a corresponding `debug_dag/debug_<name>.py`
6. Check that all new tables appear in the classification map

## Output

Report inconsistencies using this format:
```
[STALE]   node/edge — what changed and what the diagram should show instead
[MISSING] component — exists in code but not in any diagram
[OK]      component — verified accurate
```

Then provide updated Mermaid blocks for any stale sections.

## Verification Queries

```bash
# List all view files
ls src/dashboard/views/

# Check app.py routing coverage
grep "elif page ==" src/dashboard/app.py

# List all production DAGs
ls airflow/dags/

# List all debug DAGs
ls airflow/debug_dag/

# List all schema files
ls src/database/*_schema.py
```
