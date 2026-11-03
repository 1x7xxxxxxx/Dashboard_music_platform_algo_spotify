"""Local and CI must judge the SAME object: the pushed commits (class ci-gate-with-no-local-counterpart).

Type: Test
Uses: tools/dev/require_roadmap_id.py (--pre-push, --range), .pre-commit-config.yaml
Depends on: git

The commit-msg half judges the index diff; on `git commit --amend` the index equals HEAD, so an
out-of-scope commit passed locally and was refused by CI (206acd0). The pre-push hook runs
CI's `check_range` on the real commits. Hermetic: a tmp repo holding the REAL script, driven
by a subprocess with the env vars pre-commit exports for a pre-push hook.

Mutation record (2026-11-03): see the history of ci-gate-with-no-local-counterpart.
"""
import os
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "tools/dev/require_roadmap_id.py"
CHECKLIST = ".claude/dev-docs/roadmap/checklist.md"
ZERO = "0" * 40


def _checklist(*ids: str) -> str:
    rows = "\n".join(
        f"| {i} | x <!-- critic: non — outil --> <!-- scope: src/a/, src/b/ --> | P3 | m |"
        for i in ids)
    return ("## 📋 Tâches ouvertes\n\n| id | Tâche | P | Mesuré par |\n|---|---|---|---|\n"
            f"{rows}\n")


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=env, check=True)
    return r.stdout.strip()


def _commit(repo: Path, files: dict[str, str], msg: str, *extra: str) -> str:
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        _git(repo, "add", name)
    _git(repo, "commit", "-q", "--no-verify", *extra, "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "tools/dev").mkdir(parents=True)
    shutil.copy(ROOT / SCRIPT, repo / SCRIPT)  # copied, never read: the subprocess runs it
    _git(repo, "add", SCRIPT)
    base = _commit(repo, {CHECKLIST: _checklist("R300")}, "base")
    return repo, base


def _run(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = {k: v for k, v in os.environ.items() if not k.startswith("PRE_COMMIT")}
    e.update(env or {})
    return subprocess.run(["python3", SCRIPT, *args], cwd=repo, capture_output=True,
                          text=True, env=e)


def _push(repo: Path, frm: str, to: str) -> subprocess.CompletedProcess:
    return _run(repo, "--pre-push", env={"PRE_COMMIT_FROM_REF": frm, "PRE_COMMIT_TO_REF": to})


def test_an_out_of_scope_commit_is_refused_at_push_and_names_the_file(tmp_path):
    repo, base = _repo(tmp_path)
    head = _commit(repo, {"src/other/x.py": "x = 1\n"}, "R300 : x")
    r = _push(repo, base, head)
    assert r.returncode != 0 and "src/other/x.py" in r.stderr, r.stderr


def test_an_amended_out_of_scope_commit_is_still_refused(tmp_path):
    """The incident: a message-only amend of a bad commit (index == HEAD)."""
    repo, base = _repo(tmp_path)
    _commit(repo, {"src/other/x.py": "x = 1\n"}, "R300 : x")
    head = _commit(repo, {}, "R300 : x, reworded", "--amend")
    r = _push(repo, base, head)
    assert r.returncode != 0 and "src/other/x.py" in r.stderr, r.stderr


def test_an_in_scope_commit_passes(tmp_path):
    repo, base = _repo(tmp_path)
    head = _commit(repo, {"src/a/x.py": "x = 1\n"}, "R300 : x")
    assert _push(repo, base, head).returncode == 0
    head = _commit(repo, {}, "R300 : y", "--amend")
    assert _push(repo, base, head).returncode == 0


def test_a_row_opened_in_the_commit_itself_does_not_count(tmp_path):
    repo, base = _repo(tmp_path)
    head = _commit(repo, {CHECKLIST: _checklist("R300", "R301"), "src/a/y.py": "y = 1\n"},
                   "R301 : y")
    r = _push(repo, base, head)
    assert r.returncode != 0 and "R301" in r.stderr, r.stderr


def test_the_push_verdict_equals_the_ci_verdict(tmp_path):
    repo, base = _repo(tmp_path)
    good = _commit(repo, {"src/a/x.py": "x = 1\n"}, "R300 : x")
    bad = _commit(repo, {"src/other/x.py": "x = 1\n"}, "R300 : z")
    for frm, to in ((base, good), (base, bad)):
        push, ci = _push(repo, frm, to), _run(repo, "--range", f"{frm}..{to}")
        assert (push.returncode, push.stderr) == (ci.returncode, ci.stderr)
    assert _push(repo, base, bad).returncode != 0


def test_a_new_branch_is_judged_from_the_merge_base_and_a_deleted_ref_is_skipped(tmp_path):
    repo, base = _repo(tmp_path)
    _git(repo, "update-ref", "refs/remotes/origin/main", base)
    head = _commit(repo, {"src/other/x.py": "x = 1\n"}, "R300 : x")
    assert _push(repo, ZERO, head).returncode != 0
    assert _push(repo, head, ZERO).returncode == 0


def test_the_hook_is_registered_on_the_pre_push_stage_and_installed():
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [h for r in cfg["repos"] for h in r["hooks"]]
    mine = [h for h in hooks if SCRIPT in h.get("entry", "") and "--pre-push" in h["entry"]]
    assert mine and all(h["stages"] == ["pre-push"] and h.get("always_run") for h in mine)
    assert "pre-push" in cfg["default_install_hook_types"]
