Generate the documentation trio for a new feature, to preserve context across conversation compaction.

Feature name: $ARGUMENTS

## What to create

Create three files under `.claude/dev-docs/$ARGUMENTS/`:

### 1. `plan.md` — Implementation plan
Based on the current conversation, write a structured plan:
- **Objective**: one sentence on the goal
- **Affected files**: list with their roles (new / modified)
- **Implementation steps**: numbered, each step actionable in one session
- **Risks / watch-outs**: known pitfalls (e.g. ARTIST_NAME_FILTER, autocommit, imports inside DAG tasks)
- **Out of scope**: what explicitly will NOT be done

### 2. `context.md` — Technical context snapshot
Capture the key facts needed to resume work after /clear:
- DB tables involved (with key columns and UNIQUE constraints)
- Related files already read in this session
- Patterns being followed (which existing file is the reference implementation)
- Current state: what exists vs what is missing
- Open questions (if any)

### 3. `checklist.md` — Task checklist
A markdown checklist to track progress:
```markdown
## $ARGUMENTS — Checklist

### Implementation
- [ ] Step 1...
- [ ] Step 2...

### Validation
- [ ] Test locally (python airflow/debug_dag/debug_*.py or streamlit run)
- [ ] Run /review-dag or /review-db-schema if relevant
- [ ] Update DEVLOG.md

### Cleanup
- [ ] /clear context after completion
```

## After creating the files

Tell the user:
- The files are in `.claude/dev-docs/$ARGUMENTS/`
- To resume after /clear: "Read .claude/dev-docs/$ARGUMENTS/context.md and continue with the checklist"
