"""The signature of `db-connection-per-show` sees a view that opens a SECOND connection.

Type: Sub
Uses: .claude/scripts/audit_python_signatures.py (db_connection_per_show)
Depends on: nothing — fabricated views under tmp_path

Rule 9: a view opens exactly one connection. The signature counts REAL calls (AST), after its
textual predecessor was fooled by its own comments on 2026-08-22.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "aps", Path(__file__).resolve().parents[1] / ".claude/scripts/audit_python_signatures.py")
aps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aps)


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    views = tmp_path / "views"
    views.mkdir()
    (views / "two.py").write_text(
        "def show():\n    db = get_db_connection()\n    db2 = get_db_connection()\n", encoding="utf-8")
    (views / "one.py").write_text(
        "def show():\n    # get_db_connection() once more, said the comment\n"
        "    db = get_db_connection()\n", encoding="utf-8")
    assert aps.db_connection_per_show(views) == ["views/two.py: 2 appels"]
