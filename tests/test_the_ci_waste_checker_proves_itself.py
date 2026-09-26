"""`check_ci_waste.py` carries a self-test that FABRICATES each defect — this runs it.

Type: Sub
Uses: .claude/scripts/check_ci_waste.py (self_test)
Depends on: nothing — the self-test builds throwaway repositories under a temp dir

The script has proved itself on fabricated workflows since it was written (`--self-test`),
and nothing executed that proof: CI runs the checker, never its self-test (found
2026-09-26, R169). A proof nobody runs is a proof that can rot unseen.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_ci_waste", Path(__file__).resolve().parents[1] / ".claude/scripts/check_ci_waste.py")
ccw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ccw)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Twice-per-commit and no-concurrency-group, fabricated and corrected, both ways."""
    assert ccw.self_test() == 0, "check_ci_waste's own self-test went red"


def test_the_test_selector_proves_itself() -> None:
    """Same finding, second script: `select_tests.self_test()` builds a two-hop chain
    (test → intermediate → leaf) and checks the transitive closure catches it — rule 16
    rests on that selector, and its self-test was run by nothing (2026-09-26)."""
    spec = importlib.util.spec_from_file_location(
        "select_tests", Path(__file__).resolve().parents[1] / ".claude/scripts/select_tests.py")
    st = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(st)
    assert st.self_test() == 0, "select_tests' own self-test went red"


def _orphan_self_tests(root: Path) -> list[str]:
    """Scripts defining `self_test()` that no test module both imports by file and calls."""
    tests = [p.read_text(encoding="utf-8") for p in (root / "tests").glob("test_*.py")]
    out = []
    for folder in (root / ".claude" / "scripts", root / "tools"):
        for script in folder.rglob("*.py"):
            if "def self_test" not in script.read_text(encoding="utf-8", errors="ignore"):
                continue
            if not any(script.name in t and "self_test()" in t for t in tests):
                out.append(str(script.relative_to(root)))
    return sorted(out)


def test_every_self_test_is_run_by_the_suite() -> None:
    """Found twice on 2026-09-26: a proof that exists and that nothing executes. The
    suite is the only thing that runs on every commit, so it is where a self-test lives."""
    root = Path(__file__).resolve().parents[1]
    assert _orphan_self_tests(root) == [], (
        "these scripts carry a self_test() the suite never runs — add a test that calls "
        f"it: {_orphan_self_tests(root)}")


def test_the_orphan_detector_sees_an_orphan(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / ".claude" / "scripts").mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / ".claude" / "scripts" / "probe.py").write_text("def self_test():\n    return 0\n")
    assert _orphan_self_tests(tmp_path) == [".claude/scripts/probe.py"]
    (tmp_path / "tests" / "test_probe.py").write_text("# probe.py\nassert m.self_test() == 0\n")
    assert _orphan_self_tests(tmp_path) == []
