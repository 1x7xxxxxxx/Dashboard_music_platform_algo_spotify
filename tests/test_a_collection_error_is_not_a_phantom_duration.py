"""A test file that fails to import is named as such, not as phantom durations.

Type: Sub
Uses: tools/dev/check_durations_are_collectable.py
Depends on: nothing — pure parsing, no collection, no database

On 2026-09-25 the CI static job lacked FERNET_KEY and the Airflow credentials that
`src/dashboard/app.py` demands at import. Two test files failed to collect, and the
durations gate reported their 37 entries as "tests that no longer exist" — sending the
reader to regenerate a `.test_durations` that was correct. The gate now refuses on the
collection error itself, and names the files.
"""
import importlib.util
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[1] / "tools/dev/check_durations_are_collectable.py"
_spec = importlib.util.spec_from_file_location("check_durations", _TOOL)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_PYTEST_TAIL = """\
tests/test_a.py::test_one
=========================== short test summary info ============================
ERROR tests/test_the_menu_says_what_each_page_is.py - RuntimeError: FERNET_KE...
ERROR tests/test_the_setup_landing_beats_a_stale_url.py - RuntimeError: Ident...
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
"""


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    assert _mod.collection_errors(_PYTEST_TAIL) == [
        "tests/test_the_menu_says_what_each_page_is.py",
        "tests/test_the_setup_landing_beats_a_stale_url.py",
    ]


def test_a_clean_collection_reports_no_error() -> None:
    assert _mod.collection_errors("tests/test_a.py::test_one\n9703 tests collected\n") == []


def test_a_test_named_after_errors_is_not_a_collection_error() -> None:
    assert _mod.collection_errors("tests/test_x.py::test_ERROR_tests_are_named\n") == []
