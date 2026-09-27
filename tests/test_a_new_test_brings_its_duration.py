"""R250 — the commit that adds a test brings its duration (main went red on it 3× on 2026-09-27)."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _hook() -> dict | None:
    with open(ROOT / ".pre-commit-config.yaml", encoding="utf-8") as fh:   # YAML, no Python read
        cfg = yaml.safe_load(fh)
    return next((h for repo in cfg["repos"] for h in repo.get("hooks", [])
                 if h.get("id") == "test-durations-known"), None)


def test_the_commit_hook_checks_the_durations_of_staged_tests():
    hook = _hook()
    assert hook, "the pre-commit hook test-durations-known is gone"
    assert Path(hook["entry"].split()[-1]).stem == "check_durations_are_collectable"
    assert "--fix" not in hook["entry"], "a commit hook must refuse, not rewrite the suite"
    pattern = re.compile(hook["files"])
    assert pattern.search("tests/test_new_guard.py"), "a new test file would not trigger it"
    assert not pattern.search("src/dashboard/app.py")
    assert hook.get("pass_filenames", True), (
        "the staged file names tell the script it runs as the commit hook")


def test_the_hook_judges_every_tracked_test_not_only_the_staged_files():
    """R251 — the id that turned main red on 2026-09-27 lives in a file NOT staged: a
    comment added to test_the_gold_coverage_only_improves.py shifted the line number that
    test_a_comment_names_a_test_that_exists puts in its id."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_durations", ROOT / "tools/dev/check_durations_are_collectable.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    shifted = ("tests/test_a_comment_names_a_test_that_exists.py::test_a_comment_names_a_"
               "test_file_that_exists[tests/test_the_gold_coverage_only_improves.py-310-x]")
    wip = "tests/test_in_progress.py::test_x"
    assert mod.outside([shifted, wip], {"tests/test_in_progress.py"}) == [shifted], (
        "only the UNTRACKED file is left out — a tracked file beside the staged one is "
        "this commit's tree too")
