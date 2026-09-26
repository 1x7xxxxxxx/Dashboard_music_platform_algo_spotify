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


def test_view_session_adoption_sees_a_view_that_bypasses_it(tmp_path) -> None:
    """A view opening the connection by hand is seen even when a COMMENT names
    `view_session` (the grep this replaced excluded it on that comment alone)."""
    views = tmp_path / "views"
    views.mkdir()
    (views / "legacy.py").write_text(
        "# TODO migrer vers view_session\ndef show():\n    db = get_db_connection()\n")
    (views / "migrated.py").write_text(
        "def show():\n    with view_session() as (db, a):\n        get_db_connection\n"
        "    return get_db_connection() if False else None\n")
    assert aps.view_session_adoption(views) == ["legacy.py"]


def test_csv_formula_injection_sees_an_undefanged_export(tmp_path) -> None:
    (tmp_path / "raw.py").write_text("def f(df):\n    return df.to_csv()  # harmless\n")
    (tmp_path / "safe.py").write_text("def f(df):\n    return defang_formulas(df).to_csv()\n")
    assert aps.csv_formula_injection(tmp_path) == ["raw.py:2"]


def test_guide_single_os_shortcut_sees_a_shortcut_shown_to_the_artist(tmp_path) -> None:
    (tmp_path / "guide.py").write_text(
        '"""Ne jamais écrire Ctrl+U : c\'est dans la docstring, jamais rendu."""\n'
        "TEXT = 'Appuie sur Ctrl+U pour voir la source'\n"
        "OK = 'Appuie sur {{VIEW_SOURCE}}'\n")
    assert aps.guide_single_os_shortcut([tmp_path]) == ["guide.py:2"]


def test_api_partial_date_sees_a_raw_release_date(tmp_path) -> None:
    raw = tmp_path / "spotify_api.py"
    raw.write_text("def f(track):\n    release_date = track['album']['release_date']\n")
    assert aps.api_partial_date_into_date_column(raw) == ["spotify_api.py:2"]
    raw.write_text("def f(track):\n    release_date = coerce_api_date(track['album']['release_date'])\n")
    assert aps.api_partial_date_into_date_column(raw) == []
