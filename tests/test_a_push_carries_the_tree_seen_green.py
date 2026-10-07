"""R444 — a push is refused unless its tree is the tree the local suite saw green.

Type: Sub
Uses: tools/dev/pre_push_gate.py, .pre-commit-config.yaml, Makefile
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pre_push_gate", ROOT / "tools/dev/pre_push_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".gitignore").write_text(gate.STAMP + "\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / ".claude/dev-docs/roadmap").mkdir(parents=True)
    (tmp_path / ".claude/dev-docs/roadmap/checklist.md").write_text("| id |\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def _commit_all(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def test_no_green_run_means_no_push(tmp_path):
    repo = _repo(tmp_path)
    ok, why = gate.verdict(repo, _git(repo, "rev-parse", "HEAD"))
    assert not ok and "no green" in why


def test_the_tree_tested_before_the_commit_is_the_tree_pushed(tmp_path):
    repo = _repo(tmp_path)
    (repo / "app.py").write_text("x = 2\n")
    gate.stamp(repo)                       # suite ran on the uncommitted edit
    sha = _commit_all(repo, "R1 : edit")
    assert gate.verdict(repo, sha)[0]


def test_code_changed_after_the_green_run_is_refused(tmp_path):
    """The 2026-10-07 shape: green on targeted tests, then more code, then push."""
    repo = _repo(tmp_path)
    gate.stamp(repo)
    (repo / "app.py").write_text("x = 3\n")
    ok, why = gate.verdict(repo, _commit_all(repo, "R1 : more code"))
    assert not ok and "app.py" in why


def test_a_roadmap_only_commit_after_the_green_run_passes(tmp_path):
    repo = _repo(tmp_path)
    gate.stamp(repo)
    (repo / ".claude/dev-docs/roadmap/checklist.md").write_text("| id |\n| R1 |\n")
    assert gate.verdict(repo, _commit_all(repo, "Roadmap : R1 close"))[0]


def test_an_untracked_file_present_at_test_time_is_part_of_the_tested_tree(tmp_path):
    """A new module the suite imported, then forgotten at commit time, must not pass."""
    repo = _repo(tmp_path)
    (repo / "new_module.py").write_text("y = 1\n")
    gate.stamp(repo)
    _git(repo, "commit", "--allow-empty", "-qm", "R1 : forgot the new file")
    ok, why = gate.verdict(repo, _git(repo, "rev-parse", "HEAD"))
    assert not ok and "new_module.py" in why


def test_the_hook_runs_at_push_and_make_stamps_only_when_green():
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    assert "pre-push" in cfg["default_install_hook_types"]
    hooks = [h for r in cfg["repos"] for h in r["hooks"] if h["id"] == "pre-push-tested-tree"]
    assert hooks and hooks[0]["stages"] == ["pre-push"]
    assert hooks[0]["entry"].endswith("tools/dev/pre_push_gate.py")
    make = (ROOT / "Makefile").read_text()
    for target in ("test-changed:", "test:"):
        body = make.split("\n" + target, 1)[1].split("\n\n", 1)[0]
        line = next(ln for ln in body.splitlines() if "pre_push_gate.py stamp" in ln)
        # stamped only behind a success test on the suite's own exit code
        assert "rc -eq 0 ] || exit" in line or "rc -ne 0 ] ||" in line, line


def test_only_the_two_roadmap_files_are_exempt():
    """Widening EXEMPT is widening what reaches main untested — it must be a decision."""
    assert gate.EXEMPT == {".claude/dev-docs/roadmap/checklist.md",
                           ".claude/dev-docs/roadmap/archive.md"}


def test_the_other_roads_to_main_are_closed():
    """Siblings swept on 2026-10-07: the model's `--no-verify`, a clone without the hook,
    and GitHub MCP writes that reach main with no hook at all."""
    import json
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "git push --no-verify origin main"}})
    hook = subprocess.run(["python3", str(ROOT / ".claude/hooks/guard_destructive.py")],
                          input=payload, capture_output=True, text=True, cwd=ROOT)
    assert hook.returncode == 2, "the Bash guard lets the model skip the pre-push hook"
    make = (ROOT / "Makefile").read_text()
    assert "git rev-parse --git-path hooks/pre-push" in make
    deny = json.loads((ROOT / ".claude/settings.json").read_text())["permissions"]["deny"]
    for tool in ("mcp__github__push_files", "mcp__github__create_or_update_file",
                 "mcp__github__delete_file", "mcp__github__merge_pull_request"):
        assert tool in deny, tool
