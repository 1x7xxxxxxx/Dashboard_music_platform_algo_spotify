"""A change under a directory a test WALKS selects that test — whatever the walk's spelling.

Type: Sub
Uses: .claude/scripts/select_tests.py (select with a fabricated diff, scanned_patterns)
Depends on: the repository's own tests (the probes name real readers)

R338 (2026-09-29): a sweep tracing every file the suite opens found ~45 tests that
`make test-changed` never selected, because the selector knew three FORMS of directory
walk. Each probe below is a real reader it missed, now selected by containment of the
resolved directory and its pattern (code-critic R338). The last test pins the price: a
walk must not select on a file its pattern excludes, or `test-changed` stops being cheap.

Mutation record (2026-09-29): seen red with `_walk_matches` ignoring the pattern, and with
the directory family skipped (`tree = set()`).
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("select_tests",
                                               ROOT / ".claude/scripts/select_tests.py")
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)

PROBES = {
    "airflow/dags/alert_monitor.py": ["test_every_dag_can_be_called_dead",
                                      "test_the_scheduler_is_not_the_biggest_cost"],
    ".claude/dev-docs/roadmap/checklist.md": ["test_every_make_target_the_docs_name_exists"],
    ".github/workflows/ci.yml": ["test_a_cache_names_what_it_depends_on"],
    "docker-compose.example.yml": ["test_in_memory_limits_forbid_replicas"],
    ".claude/hooks/guard_destructive.py": ["test_a_blocking_hook_says_why_on_stderr"],
    # found by `make select-audit` (R338): a whole-repo reader, and an asset named by a module
    "deploy/prometheus/prometheus.yml": ["test_every_dev_doc_is_reachable",
                                         "test_an_archive_is_indexed_and_dead"],
    "assets/csv_guides/s4a/s4a_music_pannel.png": ["test_guide_pdf"],
}


@pytest.mark.parametrize("changed", sorted(PROBES))
def test_a_change_selects_the_tests_that_walk_its_directory(changed: str) -> None:
    r = st.select(ROOT, _changed=[changed])
    assert not r["all"], "the probe must not fall back to the whole suite — it proves nothing"
    missed = [t for t in PROBES[changed] if not any(t in x for x in r["tests"])]
    assert not missed, f"{changed} changed, and these readers were not selected: {missed}"


def test_the_runtime_config_forces_the_suite() -> None:
    assert st.select(ROOT, _changed=[".streamlit/config.toml"])["all"]


def test_a_walk_selects_on_what_it_reads_and_nothing_else() -> None:
    src = ('from pathlib import Path\nD = Path("airflow") / "dags"\n'
           'x = D.glob("*.py")\ny = Path(".").glob("docker-compose*.y*ml")\n')
    walks = st.scanned_patterns(src, "tests/test_x.py")
    match = lambda c: any(st._walk_matches(d, p, r, c) for d, p, r in walks)  # noqa: E731
    assert match("airflow/dags/new_dag.py") and match("docker-compose.example.yml")
    assert not match("airflow/dags/sub/deep.py"), "a non-recursive glob stops at its directory"
    assert not match("README.md"), "a root glob selects on its pattern, not on every root file"
