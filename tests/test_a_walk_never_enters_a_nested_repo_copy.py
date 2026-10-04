"""A disk walk never judges the git-ignored repo copies kept under `.claude/worktrees/`.

Type: Sub
Uses: tools/dev/repo_files.py, git (a throwaway repository under `tmp_path`)
Depends on: the seven walking sites named below, each called with `root` = the tmp repo
Persists in: nothing

The defect — measured on 2026-10-04 at a92856f9
------------------------------------------------
Claude Code keeps its agent worktrees INSIDE the repository, under
`.claude/worktrees/<name>/` — full copies of the repo, ignored only by the local
`.git/info/exclude`, never present in CI. Every guard that walked the disk from the repo
root or from `.claude/` without asking git went down into them:
`test_a_commit_message_is_not_fed_through_stdin.py` failed on four files, all under
`.claude/worktrees/*/tests/` (and never scanned the real `tests/`), and
`test_no_rex_lives_outside_the_validator.py` listed every rex-bearing `.md` of both copies.
Class: `a-test-that-only-ever-ran-on-its-authors-machine` (récidive, third form: an
ignored copy of the repo nested inside a walked root).

Why the guard runs in a tmp repo
--------------------------------
On CI there is no worktree, so a guard reading the real tree is green on nothing. Each
site is called on a fabricated repo whose `.claude/worktrees/x/` holds a deliberately
VIOLATING file for it, next to a legitimate one in the real tree — so the guard proves
both that the copy is skipped and that the walk still reads something.

The execution net
-----------------
`tests/conftest.py::_no_walk_into_a_nested_repo_copy` wraps `Path.rglob/glob`, `os.walk`
and `glob.glob/iglob` during EVERY test and fails a test whose walk yields a path inside
`<repo>/.claude/worktrees/`. It binds whatever the walker's receiver is called — but it
is vacuous where no worktree exists (CI), which is why `test_the_probe_*` below drive it
on the tmp repo. Its limits: walks inside a subprocess, a walk bound before the fixture
(`from os import walk`), and skipped tests are invisible to it.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

from tools.dev import repo_files as rf

ROOT = Path(__file__).resolve().parents[1]
_COPY = ".claude/worktrees/x"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


_COMMIT_STDIN = "#!/bin/sh\ngit commit -F -\n"
_REX_MD = "---\nname: t\nrex:\n  - date: 2026-10-04\n    issue: x\n    fix: y\n---\nbody\n"
_ECHO_BACKTICK = '#!/bin/sh\necho "voir `pwd` pour le chemin"\n'
_CONFTEST = ("import os, sys\nsys.path.insert(0, 'zz_only_in_copy')\n"
             "_W = os.environ.get('PYTEST_XDIST_WORKER', 'main')\n")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo whose `.claude/worktrees/x/` is an ignored copy carrying every violation."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("**/.claude/worktrees/\n", encoding="utf-8")
    # the real tree: one legitimate (or deliberately caught) file per site
    _write(root, "tools/real.sh", _COMMIT_STDIN)                      # commit site: a REAL hit
    _write(root, ".claude/skills/real.md", _REX_MD)                   # rex site: a REAL orphan
    _write(root, "tools/ok.sh", "#!/bin/sh\necho 'fine'\n")
    _write(root, "tests/conftest.py", "import os\n")                  # no xdist, no sys.path
    _write(root, ".claude/hooks/h.py", "x = 1\n")
    (root / "zz_only_in_copy").mkdir()                                # a root ONLY the copy declares
    _write(root, "Makefile", "all:\n\techo ok\n")
    _write(root, "tools/dev/tracked_then_deleted.py", "x = 1\n")
    _write(root, "deleted_name.py", "x = 1\n")
    _write(root, "present.py", "x = 1\n")
    # the ignored copy: one VIOLATING file per site
    _write(root, f"{_COPY}/tools/c.sh", _COMMIT_STDIN)
    _write(root, f"{_COPY}/tests/t.py", "CMD = 'git commit -F -'\n")
    _write(root, f"{_COPY}/.claude/skills/ghost.md", _REX_MD)
    _write(root, f"{_COPY}/tools/bad.sh", _ECHO_BACKTICK)
    _write(root, f"{_COPY}/tests/conftest.py", _CONFTEST)
    _write(root, f"{_COPY}/src/m.py", "x = 1\n")
    _write(root, f"{_COPY}/only_in_copy.py", "x = 1\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    # m5's shape: still in the index, gone from the disk
    (root / "tools/dev/tracked_then_deleted.py").unlink()
    (root / "deleted_name.py").unlink()
    return root


def _nested(paths) -> list[str]:
    return [str(p) for p in paths if _COPY in Path(p).as_posix()]


def test_the_fixture_really_holds_the_copy(repo: Path) -> None:
    """Non-vacuity: the copy exists on disk, and git ignores it."""
    on_disk = [p for p in repo.rglob("*") if p.is_file()]
    assert _nested(on_disk), "the decoy copy was not written — every check below is vacuous"
    assert not _nested(rf.repo_files(repo)), "git does not ignore the decoy copy"


def test_the_commit_stdin_guard_skips_the_copy(repo: Path) -> None:
    mod = _load("_commit_guard", "tests/test_a_commit_message_is_not_fed_through_stdin.py")
    assert not _nested(mod._fichiers(repo)), mod._fichiers(repo)
    assert mod._sites(repo) == ["tools/real.sh"]


def test_the_rex_guard_skips_the_copy(repo: Path) -> None:
    mod = _load("_rex_guard", "tests/test_no_rex_lives_outside_the_validator.py")
    assert mod._orphans(repo, set()) == [".claude/skills/real.md"]


def test_the_description_guard_skips_the_copy(repo: Path) -> None:
    mod = _load("_desc_guard", "tests/test_a_description_does_not_execute.py")
    files = mod._shell_files(repo)
    assert not _nested(files), files
    assert repo / "tools/ok.sh" in files


def test_the_engineering_loop_check_reads_the_tree_not_a_copy_nor_the_index(repo: Path) -> None:
    mod = _load("_loop_guard", "tests/test_the_engineering_loop_sends_real_prompts.py")
    src = ("deploy_order: [ 'run `only_in_copy.py`, `tools/dev/tracked_then_deleted.py`, "
           "`deleted_name.py` and `present.py`' ]")
    missing = mod._missing(src, repo)
    assert "only_in_copy.py" in missing, "a script present only in the ignored copy was found"
    assert "tools/dev/tracked_then_deleted.py" in missing, "an indexed-but-deleted path was found"
    assert "deleted_name.py" in missing, "an indexed-but-deleted script name was found"
    assert "present.py" not in missing


def test_select_tests_prunes_the_copy(repo: Path) -> None:
    st = _load("_select_tests", ".claude/scripts/select_tests.py")
    assert not _nested(st._trouve_conftests(repo))
    assert repo / "zz_only_in_copy" not in st.racines_declarees(repo), (
        "the copy's conftest declared an import root")
    walked = st._walk_python(repo, [repo, repo / ".claude" / "hooks"])
    assert repo / ".claude/hooks/h.py" in walked, "the walk no longer reaches `.claude/hooks`"
    assert not _nested(walked), walked


def test_check_ci_waste_prunes_the_copy(repo: Path) -> None:
    cw = _load("_check_ci_waste", ".claude/scripts/check_ci_waste.py")
    assert cw._conftests_xdist(repo) == [], "the copy's xdist conftest was counted"


def test_the_probe_sees_a_walk_into_the_copy(repo: Path) -> None:
    """The conftest net, driven where a copy exists — on CI it would see nothing."""
    sink: list[str] = []
    undo = rf.install_walk_probe(repo, sink)
    try:
        list(repo.rglob("*.md"))
        list(os.walk(repo / ".claude"))
    finally:
        undo()
    assert any("ghost.md" in s for s in sink), sink
    assert any(s.endswith("worktrees/x") or "/worktrees/x/" in s for s in sink), sink


def test_the_probe_is_silent_on_a_walk_through_git(repo: Path) -> None:
    sink: list[str] = []
    undo = rf.install_walk_probe(repo, sink)
    try:
        rf.repo_files(repo, "*.md")
        list((repo / "tools").rglob("*"))
    finally:
        undo()
    assert sink == []


def test_the_probe_is_installed_for_every_test() -> None:
    """The net binds only if the conftest fixture actually wrapped the walkers."""
    assert "install_walk_probe" in Path.rglob.__qualname__, Path.rglob.__qualname__
    assert "install_walk_probe" in os.walk.__qualname__, os.walk.__qualname__
