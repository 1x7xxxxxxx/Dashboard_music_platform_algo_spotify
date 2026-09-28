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
    # R319: the hook may MEASURE the missing durations (`--fix-once`), but it still refuses
    # the commit once — never `--fix`, whose green exit would let a rewrite through unseen.
    assert "--fix" not in hook["entry"] and hook.get("args", []) in ([], ["--fix-once"]), (
        "a commit hook must refuse — measuring is allowed, a silent rewrite is not")
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


def test_the_hooks_remedy_always_refuses_the_commit_once():
    """R319 — measuring the missing durations never turns the hook green by itself."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_durations", ROOT / "tools/dev/check_durations_are_collectable.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.fix_once({}, ["tests/test_x.py::t"], fixer=lambda f, s: 0,
                        recheck=lambda: 0) == 1, "a successful measure must still refuse once"
    assert mod.fix_once({}, ["tests/test_x.py::t"], fixer=lambda f, s: 2,
                        recheck=lambda: 0) == 1
