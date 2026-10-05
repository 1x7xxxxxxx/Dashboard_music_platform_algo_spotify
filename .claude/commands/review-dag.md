---
invocation: "manual — /review-* : audit lancé à la main par le propriétaire, nommé par CLAUDE.md (response-protocol) ; décidé R413, gardé"
rex: []
---

You are an Airflow DAG pattern reviewer for this project. Audit all DAGs for structural consistency.

## Steps

1. **List all files** in `airflow/dags/`.

2. **For each production DAG** in `airflow/dags/`, verify:
   - `sys.path.insert(0, '/opt/airflow')` is present at the top.
   - `default_args` contains at minimum: `owner`, `depends_on_past=False`, `retries=2`, `retry_delay=timedelta(minutes=10)`.
   - DAG `dag_id` matches the filename (e.g., `soundcloud_daily.py` → `dag_id='soundcloud_daily'`).
   - Collector and `src.*` imports are **inside** task functions (not at module level) to prevent Airflow parse errors.

4. **Cross-check**:
   - DAGs referenced in `src/utils/airflow_trigger.py` (the `dags` list in `trigger_all_dags()`) exist in `airflow/dags/`.
   - DAGs listed in `src/dashboard/app.py` (`show_data_collection_panel`) match actual DAG ids.

## Output format

For each issue found, report:
```
[SEVERITY] file — description
```
Severity: `ERROR` (will break at runtime), `WARNING` (pattern deviation), `MISSING` (file absent).

End with a summary table: DAG name | debug file ✅/❌ | default_args ✅/❌ | imports inside tasks ✅/❌.
