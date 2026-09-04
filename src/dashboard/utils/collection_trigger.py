"""Launch this tenant's collections — one rule, several buttons.

Type: Utility
Uses: airflow_trigger, collection_progress, safe_error
Triggers: the sidebar panel, the home setup step
Depends on: COLLECTION_DAGS
Persists in: nothing (Airflow runs + session state for the progress panel)

Extracted from `app.show_data_collection_panel` on 2026-09-04, when the home page's
fourth setup step needed to launch a collection itself. The step NAMED the action and
sent the artist to the sidebar to perform it — an instruction is what you write when
the button is somewhere else.

Everything that matters lives here because it is easy to get wrong in a second copy:

* **every trigger carries `conf={'artist_id': …}`**. Without it the collectors run
  fleet-wide, and the CSV watchers default to `artist_id = 1` — i.e. straight into the
  ADMIN's tenant, which is the leak two beta sessions were spent on;
* **a refusal says WHY**. A bare ❌ is what made « toutes les credentials ont échoué »
  impossible to act on during a live session;
* **`safe_error`, never `{e}`**: `trigger_dag` talks to Airflow's REST API with
  credentials, and this message is rendered TO THE ARTIST.
"""
from __future__ import annotations

from typing import Optional


def trigger_all_collections(artist_id: Optional[int], airflow_trigger,
                            collection_dags) -> tuple[dict, dict]:
    """Fire every collection DAG for ONE tenant. Returns (launched, not_launched)."""
    from src.utils.safe_error import safe_error

    launched: dict[str, str] = {}
    not_launched: dict[str, str] = {}
    for dag_id, _label in collection_dags:
        try:
            conf = {'artist_id': artist_id} if artist_id is not None else {}
            result = airflow_trigger.trigger_dag(dag_id, conf=conf)
            if result.get('success'):
                # The cached "latest run per DAG" is stale the instant a run starts.
                from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag
                cached_last_run_per_dag.clear()
                if result.get('dag_run_id'):
                    launched[dag_id] = result['dag_run_id']
            else:
                not_launched[dag_id] = str(
                    result.get('error', result.get('message', '')) or '')
        except Exception as e:      # noqa: BLE001 — a refusal must still be reported
            not_launched[dag_id] = safe_error(e)
    return launched, not_launched
