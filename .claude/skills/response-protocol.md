# Skill: Response Protocol

Applies to ALL responses, ALL files, ALL code. No exceptions.

---

## Rule 1: Language

- All code comments, docstrings, variable names, inline documentation: **English exclusively**
- All markdown files in this repository: **English exclusively**
- Exception: user-visible Streamlit UI strings may use the product's target language
- Action: if existing French text is encountered in a file being edited, translate it in the same edit

---

## Rule 2: Objective Neutrality

- Technical feedback is cold and factual: describe behavior and consequences, not quality judgments
- When a problem is identified: state what it does wrong and what the consequence is
- When proposing a solution: enumerate at least 2 alternatives with their trade-offs before recommending one
- **No vibe-coding**: do not implement a feature without first reading the relevant data model and existing patterns
- **No agreement bias**: if a user's proposed approach has a known failure mode, state it — even if the user seems committed to it

### Example (wrong)
> "Great approach! Let's add error handling to make this more robust."

### Example (correct)
> "The current implementation has no retry on transient DB errors. Two alternatives:
> 1. `@retry_on_db_error` decorator (existing in `src/utils/retry.py:L12`) — applies transparently
> 2. Inline `try/except psycopg2.OperationalError` — more explicit, higher duplication
> Option 1 is consistent with the project pattern. Option 2 is used only in `instagram_api_collector.py`."

---

## Rule 3: Relational Classification

Every new file or module must be labeled in its docstring using this taxonomy.

### Type Taxonomy

| Type | Definition | Examples |
|---|---|---|
| **Core** | Foundational — depended on by many, rarely changes | `PostgresHandler`, `app.py`, `init_db.sql` |
| **Feature** | A user-visible capability with its own lifecycle | A view file, a production DAG, a collector |
| **Sub** | Helper to exactly one Feature — no direct user contact | A CSV parser, a debug DAG, a schema file |
| **Hook** | Triggered by system events, not called directly | `.claude/hooks/*.py`, Airflow failure callbacks |
| **Utility** | Shared, stateless helper — no business logic | `config_loader.py`, `retry.py`, `error_handler.py` |

### Dependency Vocabulary (use in docstrings)

| Verb | Meaning |
|---|---|
| `uses` | Calls a function or method from another module |
| `triggers` | Causes another process to execute (DAG run, Airflow task) |
| `depends on` | Cannot function if the dependency is absent |
| `persists in` | Writes to a storage system |

### Docstring Format

```python
"""
Type: Feature
Uses: get_db_connection, db.fetch_df
Depends on: saas_artists (artist_id must exist in session state)
Persists in: PostgreSQL spotify_etl (read-only view)
"""
```

---

## Mandatory Background Deliverables

After every substantive response (file created, file edited, architectural decision made), spawn a **single background general-purpose agent** to update these 4 files in one pass:

1. **`.claude/dev-docs/architecture.md`** — update Mermaid diagrams (macro + micro) to reflect the change
2. **`.claude/dev-docs/retro.md`** — append one entry: `## YYYY-MM-DD HH:MM` + Changed/Why/Decisions/Status
3. **`.claude/dev-docs/roadmap/checklist.md`** — mark completed items, add newly discovered work items
4. **`DEVLOG.md`** — append session summary entry (Why, What changed, Technical choices, Status)

The agent must complete all 4 updates in a single execution pass before exiting.
It does not interact with the user and does not ask for clarification.

**Do NOT spawn the background agent when:**
- The response is purely conversational (no files changed)
- The task reads only 2–3 files (do it inline instead)
- The sub-agents depend on each other's immediate output in the same turn
- The goal is to "verify everything is okay" (too vague — be specific or skip)

---

## Priority Tiers

When multiple items compete for attention:

| Tier | Label | Definition |
|---|---|---|
| P1 | Blocking | Data missing, crash, or security issue |
| P2 | Data integrity | Incorrect data, missing constraints, autocommit bypass |
| P3 | UX / Features | Missing functionality, user-facing improvements |
| P4 | Tech debt | Refactoring, CI/CD, deployment, non-urgent cleanup |

Resolve P1 before P2, P2 before P3. Never address P4 during a session focused on P1.
