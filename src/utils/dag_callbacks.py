"""The ONE failure callback of every DAG — mail the owner, and register the defect.

Type: Utility
Uses: src/utils/email_alerts.dag_failure_callback, src/utils/error_registry.record_error
Triggers: `on_failure_callback` of every DAG in airflow/dags/
Persists in: app_error_log (one row per fingerprint)

R265 (owner notes L67-69 : « API et DAG dans app_error_log »). Twelve DAGs carried the
same six-line wrapper around `dag_failure_callback`, and `app_error_log` was fed by the
dashboard alone: a DAG that failed every night left a mail, never a defect in the
registry `make error-inbox` reads. Critic verdict (critic-2026-09-27.md, R265 b): factor
the callbacks FIRST, then add `record_error` once.

A callback must never raise — Airflow would log the callback's own failure over the
task's — so each of the two effects is isolated from the other.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _page(context) -> str:
    """`dag:<dag_id>.<task_id>` — where the defect lives, for the registry's grouping."""
    dag = context.get("dag")
    ti = context.get("task_instance")
    return f"dag:{getattr(dag, 'dag_id', '?')}.{getattr(ti, 'task_id', '?')}"


def _tenant(context):
    """The tenant of a per-artist run (`conf={'artist_id': …}`), else None."""
    run = context.get("dag_run")
    conf = getattr(run, "conf", None) or {}
    try:
        return int(conf["artist_id"]) if conf.get("artist_id") is not None else None
    except (TypeError, ValueError):
        return None


def on_failure(context) -> None:
    """Mail, then register. Never raises."""
    from src.utils.safe_error import safe_error
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as exc:      # noqa: BLE001 — a callback never raises
        logger.error("dag failure mail: %s", safe_error(exc))

    exc = context.get("exception")
    if not isinstance(exc, BaseException):
        return
    db = None
    try:
        from src.database.postgres_handler import PostgresHandler
        from src.utils.error_registry import record_error
        db = PostgresHandler.from_env_or_config()
        record_error(db, _page(context), exc, artist_id=_tenant(context),
                     environment="airflow")
    except Exception as err:      # noqa: BLE001 — the registry is best effort here
        logger.error("dag failure registry: %s", safe_error(err))
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:      # noqa: BLE001
                pass
