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


# ── 2026-10-04 — an untracked file named in a TRACKED test's id ──────────────────────
# Three tracked meta-tests walk the disk and put every test file they find in their ids;
# about ten more walk `src/` and `tools/`. The file-only predicate let another session's
# untracked `tests/test_X.py` refuse every commit, and `--fix-once` measured those ids
# into the tracked `.test_durations` — phantoms for CI. Every id FORM below was measured
# by collecting this suite with untracked probe files under tests/, src/ and tools/.

def _load():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_durations", ROOT / "tools/dev/check_durations_are_collectable.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_WIP = {"tests/test_wip.py", "src/dashboard/views/wip.py"}
_SHIFTED = ("tests/test_a_comment_names_a_test_that_exists.py::test_a_comment_names_a_"
            "test_file_that_exists[tests/test_the_gold_coverage_only_improves.py-310-x]")
_NAMING_WIP = {
    "basename": "tests/test_no_test_deletes_a_module.py::test_a_test_restores_what_it_"
                "borrows_from_sys_modules[test_wip.py]",
    "tests path": "tests/test_no_test_stubs_an_installed_package.py::test_no_installed_"
                  "package_is_replaced_by_a_mock[tests/test_wip.py]",
    "src path": "tests/test_a_view_opens_on_one_decision.py::test_a_view_does_not_open_"
                "on_a_wall_of_charts[src/dashboard/views/wip.py]",
    "stem": "tests/test_the_views_map_lists_every_view.py::test_every_view_is_named_in_"
            "the_views_map[wip]",
    "deduplicated": "tests/test_dag_fleet_isolation.py::test_fleet_loops_outside_the_"
                    "dags_are_isolated[wip.py0]",
    "own file": "tests/test_wip.py::t",
}


def test_an_id_that_names_an_untracked_file_is_left_out_and_only_that():
    mod = _load()
    # `__init__.py` is a name a TRACKED file answers to: an untracked one never claims it.
    # And a scratch `x.py` must not claim the `x` token of R251's shifted id.
    shared = "tests/test_a_handler_is_built_with_its_arguments.py::t[__init__.py]"
    kept = mod.outside([*_NAMING_WIP.values(), _SHIFTED, shared],
                       _WIP | {"src/new/__init__.py", "x.py"}, {"__init__.py", "__init__"})
    assert kept == [_SHIFTED, shared], (
        "an id naming an untracked file — as its FILE, or in its [param] by path, "
        "basename, stem or pytest-deduplicated name — must be left out, and nothing else: "
        f"kept {kept}")


def test_the_untracked_set_is_the_whole_repo_and_not_the_ignored_files(tmp_path, monkeypatch):
    import subprocess
    mod = _load()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for f in ("src/x.py", "tests/test_new.py", "tests/test_kept.py", "ignored.py",
              ".gitignore"):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("ignored.py\n" if f == ".gitignore" else "")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore", "tests/test_kept.py"],
                   check=True)
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    assert mod.untracked_files() == {"src/x.py", "tests/test_new.py"}, (
        "an untracked file under src/ adds ids to tracked tests exactly as a test file "
        "does; an ignored one is no one's work")


def _run_main(mod, monkeypatch, tmp_path, argv, durations, collected):
    import json
    import subprocess
    tracked = [f"tests/test_a.py::t[{i}]" for i in range(1000)]
    dur = tmp_path / ".test_durations"
    dur.write_text(json.dumps({**{k: 0.01 for k in tracked}, **durations}))
    stdout = "\n".join([*tracked, *collected, "1006 tests collected"])
    measured: list = []
    monkeypatch.setattr(mod, "_DUR", dur)
    monkeypatch.setattr(mod, "_collect",
                        lambda: subprocess.CompletedProcess([], 0, stdout, ""))
    monkeypatch.setattr(mod, "untracked_files", lambda: {"tests/test_wip.py"})
    monkeypatch.setattr(mod, "tracked_names", lambda: set())
    monkeypatch.setattr(mod, "fix", lambda f, s: measured.append(sorted(s)) or 0)
    monkeypatch.setattr(mod, "main_check_again", lambda: 0)
    monkeypatch.setattr(mod.sys, "argv", ["check", *argv])
    return mod.main(), measured


_META = [_NAMING_WIP["basename"], _NAMING_WIP["tests path"], _NAMING_WIP["own file"]]


def test_the_hook_neither_judges_nor_measures_an_untracked_files_ids(tmp_path, monkeypatch):
    mod = _load()
    rc, measured = _run_main(mod, monkeypatch, tmp_path, ["--fix-once", "tests/test_a.py"],
                             {}, _META)
    assert (rc, measured) == (0, []), (
        "another session's untracked test refused a commit that does not touch it, or "
        f"`--fix-once` measured it into the tracked .test_durations: rc={rc} {measured}")
    new = "tests/test_a.py::t_new"
    rc, measured = _run_main(mod, monkeypatch, tmp_path, ["--fix-once", "tests/test_a.py"],
                             {}, [*_META, new])
    assert (rc, measured) == (1, [[new]]), (
        f"the hook must measure the tracked missing id, and only it: {measured}")


def test_a_staged_durations_file_with_an_untracked_files_entries_is_refused(
        tmp_path, monkeypatch, capsys):
    mod = _load()
    rc, measured = _run_main(mod, monkeypatch, tmp_path, ["--fix-once", ".test_durations"],
                             {k: 0.1 for k in _META}, _META)
    assert (rc, measured) == (1, []), (
        "a staged .test_durations carrying durations of untracked files would reach CI "
        "as phantoms — the hook must refuse it")
    assert _NAMING_WIP["tests path"] in capsys.readouterr().out


def test_the_manual_fix_still_measures_untracked_files_and_says_so(
        tmp_path, monkeypatch, capsys):
    mod = _load()
    rc, measured = _run_main(mod, monkeypatch, tmp_path, ["--fix"], {}, _META)
    assert measured == [sorted(_META)], "`make test-durations-missing` measures before git add"
    assert "HORS de l'index" in capsys.readouterr().out, "…and names what it wrote"


def test_main_leaves_out_an_untracked_test_and_judges_a_tracked_one(tmp_path, monkeypatch):
    """R368 — REQ-TEST-01 tested the FUNCTION `outside()`; a `main()` that stopped calling
    it stayed green. Here the hook's whole path runs: an untracked test without a duration
    passes, a tracked one without a duration is refused."""
    import importlib.util
    import json
    import subprocess
    spec = importlib.util.spec_from_file_location(
        "check_durations_main", ROOT / "tools/dev/check_durations_are_collectable.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    known = [f"tests/test_known.py::test_{i}" for i in range(1000)]
    dur = tmp_path / ".test_durations"
    dur.write_text(json.dumps({k: 0.1 for k in known}), encoding="utf-8")
    monkeypatch.setattr(mod, "_DUR", dur)
    monkeypatch.setattr(mod, "untracked_files", lambda: {"tests/test_wip.py"})
    monkeypatch.setattr(mod, "tracked_names",
                        lambda: {"tests", "test_known.py", "test_known", "test_new.py", "test_new"})
    monkeypatch.setattr(mod.sys, "argv", ["check", "tests/test_known.py"])

    def collected(extra):
        return lambda: subprocess.CompletedProcess([], 0, "\n".join(known + extra), "")
    monkeypatch.setattr(mod, "_collect", collected(["tests/test_wip.py::test_x"]))
    assert mod.main() == 0, "an UNTRACKED test is not this commit's — the hook must leave it out"
    monkeypatch.setattr(mod, "_collect", collected(["tests/test_new.py::test_x"]))
    assert mod.main() == 1, "a TRACKED test without a duration must be refused"
