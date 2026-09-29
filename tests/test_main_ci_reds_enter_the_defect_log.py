"""The reds of main's CI enter the defect log as `tree: clean` — parsed from the real log shape.

Type: Sub
Uses: tools/dev/import_ci_reds.py (nodes, events_of, new_only, stamp)
Depends on: nothing — a fixture in the exact `gh run view --log-failed` shape

R337 (2026-09-29). Every line of `--log-failed` starts with `job<TAB>step<TAB>timestamp `;
the session regex, anchored on `^FAILED`, would have read nothing there and marked every red
run as imported — a green importer over an empty read (code-critic R337).

Mutation record (2026-09-29): seen red with the prefix strip removed from `nodes`, and with
`events_of` turning a failed run with zero nodes into an empty verdict with no note.
"""
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "import_ci_reds", Path(__file__).resolve().parents[1] / "tools/dev/import_ci_reds.py")
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)

LOG = ("Suite 1/6\tUNKNOWN STEP\t2026-09-29T03:57:10.4238007Z FAILED tests/test_a.py::test_x"
       " - AssertionError: boom\n"
       "Suite 6/6\tUNKNOWN STEP\t2026-09-29T03:52:29.3859116Z FAILED tests/test_b.py::test_y"
       "@shared_db_tenant_identity - AssertionError\n"
       "Portes statiques\tUNKNOWN STEP\t2026-09-29T03:57:29.1Z            FAILED tests/test_a.py"
       "::test_x - replayed without .env\n"
       "Suite 1/6\tUNKNOWN STEP\t2026-09-29T03:57:11Z 1 failed, 900 passed\n")
RED = {"databaseId": 7, "conclusion": "failure", "updatedAt": "2026-09-29T04:00:00Z"}


def test_the_real_log_shape_yields_the_failed_nodes() -> None:
    assert ci.nodes(LOG) == ["tests/test_a.py::test_x", "tests/test_b.py::test_y"]


def test_a_red_run_becomes_clean_reds_and_a_green_run_proves_the_suite() -> None:
    reds, note = ci.events_of(RED, LOG)
    assert note is None and {e["tree"] for e in reds} == {"clean"}
    assert reds[0]["ts"] == "2026-09-29T04:00:00.000+00:00" and reds[0]["session"] == "ci:7"
    [green], _ = ci.events_of(dict(RED, conclusion="success"), None)
    assert green["scope"] == "suite" and green["kind"] == "test_green"
    assert ci.events_of(dict(RED, conclusion="cancelled"), None) == ([], None)


def test_a_red_run_without_test_nodes_is_said_not_skipped() -> None:
    events, note = ci.events_of(RED, "Gates\tstep\t2026-09-29T03:00:00Z ruff: E501\n")
    assert events == [] and note and "0 test nodes" in note


def test_a_second_import_writes_nothing_new(tmp_path) -> None:
    log = tmp_path / "defects.jsonl"
    reds, _ = ci.events_of(RED, LOG)
    log.write_text("".join(json.dumps(e) + "\n" for e in reds))
    assert ci.new_only(reds, log) == []
