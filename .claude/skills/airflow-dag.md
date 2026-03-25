# Skill: Airflow DAG

Injected when prompt contains: "dag", "airflow", "collector", "pipeline", "scheduler"

---

## Relational Classification

- **Type**: Feature (production DAG) / Sub (debug DAG)
- **Triggers**: Airflow scheduler → PythonOperator → collector
- **Persists in**: PostgreSQL `spotify_etl` via `PostgresHandler.upsert_many()`
- **Depends on**: `src/collectors/<platform>.py`, `src/utils/credential_loader.py`

---

## Mandatory Structure (every production DAG)

```python
import sys
sys.path.insert(0, '/opt/airflow')            # 1. Always first — enables src/ imports

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {                              # 2. Minimum 4 keys
    "owner": "data_team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

dag = DAG(
    "my_dag_name",                            # 3. dag_id must match filename exactly
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
)

def collect_data(**context):
    from src.collectors.my_collector import MyCollector  # 4. imports INSIDE task function
    from src.utils.credential_loader import load_platform_credentials
    # ... task logic

task = PythonOperator(
    task_id="collect_data",
    python_callable=collect_data,
    dag=dag,
)
```

---

## Credential Pattern (Brick 6 — multi-tenant)

```python
def collect_data(**context):
    from src.utils.credential_loader import load_platform_credentials
    creds = load_platform_credentials(artist_id=1, platform="spotify")
    # creds is a dict with platform-specific keys
```

---

## Failure Callback

```python
from src.utils.email_alerts import dag_failure_callback

default_args = {
    ...
    "on_failure_callback": dag_failure_callback,
}
```

---

## Debug DAG Rules

- File location: `airflow/debug_dag/debug_<name>.py`
- No Airflow DAG/Operator imports in the main execution path
- Must be runnable directly: `python airflow/debug_dag/debug_<name>.py`
- Mirrors production logic exactly — same collector, same DB schema

```python
# debug_my_dag.py
import sys
sys.path.insert(0, '/opt/airflow')

from src.collectors.my_collector import MyCollector
# ... run the same logic inline, no DAG wrapper
```

---

## Checklist Before Creating a DAG

- [ ] `sys.path.insert(0, '/opt/airflow')` at top of file
- [ ] `default_args` has all 4 mandatory keys
- [ ] `dag_id` matches filename (without `.py`)
- [ ] All `src.*` imports are inside task functions
- [ ] `on_failure_callback` set
- [ ] `debug_dag/debug_<name>.py` created and runnable
- [ ] DAG id does not collide with existing DAGs

---

## Reference Implementations

| Pattern | File |
|---|---|
| Full parameterized DAG | `airflow/dags/spotify_api_daily.py` |
| CSV watcher with BranchOperator | `airflow/dags/s4a_csv_watcher.py` |
| ML scoring with model load | `airflow/dags/ml_scoring_daily.py` |
| Debug mirror | `airflow/debug_dag/debug_spotify_api.py` |

---

## Cross-Cutting Rules

1. **Language**: English in all variable names, comments, docstrings
2. **Neutrality**: Describe failures as data conditions, not "errors" unless they are exceptions
3. **Classification**: Add docstring with Type/Triggers/Persists in at top of every new DAG file
