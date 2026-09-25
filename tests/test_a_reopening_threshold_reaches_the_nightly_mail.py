"""A crossed R87 threshold reaches the 23:00 mail instead of dying in a log line.

Type: Sub
Uses: airflow/dags/alert_monitor.py (nightly_maintenance, send_consolidated_alert)
Depends on: nothing — the wrapper is extracted by AST and run with a stub task instance

Measured 2026-09-25: `nightly_maintenance.run()` computed `reopening_triggers` every night
and wrote them with `logger.warning` only. The mail — the one surface the owner reads —
never carried them.
"""
import ast
import types
from pathlib import Path

_DAG = Path(__file__).resolve().parents[1] / "airflow/dags/alert_monitor.py"


class _TI:
    def __init__(self) -> None:
        self.pushed: dict = {}

    def xcom_push(self, key: str, value: object) -> None:
        self.pushed[key] = value


def _wrapper():
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "nightly_maintenance")
    mod = types.ModuleType("maintenance_under_test")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<test>", "exec"), mod.__dict__)  # noqa: S102
    return mod.nightly_maintenance


def test_the_detector_sees_the_defect_it_is_written_for(monkeypatch) -> None:
    """A crossed threshold is pushed for the mail; a quiet night pushes an empty list."""
    import src.utils.nightly_maintenance as nm

    monkeypatch.setattr(nm, "run", lambda: {"reopening_triggers": ["p95 rerun > 2 s sur 14 jours"]})
    ti = _TI()
    _wrapper()(task_instance=ti)
    assert ti.pushed.get("reopening_triggers") == ["p95 rerun > 2 s sur 14 jours"]

    monkeypatch.setattr(nm, "run", lambda: {"complete": True})
    ti = _TI()
    _wrapper()(task_instance=ti)
    assert ti.pushed.get("reopening_triggers") == []


def test_the_mail_pulls_and_shows_the_threshold() -> None:
    src = _DAG.read_text(encoding="utf-8")
    body = src[src.index("def send_consolidated_alert("):]
    assert "task_ids='nightly_maintenance', key='reopening_triggers'" in body
    assert "Seuil de réouverture R87 franchi" in body
