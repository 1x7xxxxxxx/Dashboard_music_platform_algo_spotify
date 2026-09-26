"""Every `trigger_dag(...)` from the dashboard carries `conf={'artist_id': …}`.

Type: Sub
Uses: .claude/scripts/check_dag_trigger_scope.py (unscoped_triggers)
Depends on: nothing — fabricated dashboard code under tmp_path

Class `dag-trigger-without-tenant-scope`: the « Lancer TOUTES les collectes » button fired
every DAG for every tenant, rendered before any role gate.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "cdts", Path(__file__).resolve().parents[1] / ".claude/scripts/check_dag_trigger_scope.py")
cdts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdts)


def test_the_real_dashboard_scopes_every_trigger() -> None:
    assert cdts.unscoped_triggers() == []


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    """A trigger with no conf, and one whose conf names no tenant, are seen; a literal
    `{'artist_id': a}` and a VARIABLE built with it (the collection_trigger shape, the
    first version's false positive) are not."""
    (tmp_path / "view.py").write_text(
        "def f(c, a):\n"
        "    c.trigger_dag('spotify_daily')\n"
        "    c.trigger_dag('x', conf={'force': True})\n"
        "    c.trigger_dag('y', conf={'artist_id': a})\n"
        "    conf = {'artist_id': a} if a else {}\n"
        "    c.trigger_dag('z', conf=conf)\n", encoding="utf-8")
    assert cdts.unscoped_triggers(tmp_path) == ["view.py:2", "view.py:3"]
