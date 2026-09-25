"""A commit that writes a class or a `(récidive)` line needs a REAL sweep in the transcripts.

Type: Sub
Uses: .claude/hooks/require_sweep_before_catalogue.py
Depends on: git (a throwaway repo), fabricated transcripts — no network, no database

The rules said « Spawn sibling-sweeper before the fix » and « ≥ 2 findings -> run
engineering-loop ». Measured 2026-09-25: the loop had never run once, and the only
check on a sweep was the `swept:` text of the entry. The hook refuses the commit that
closes the loop without it; these tests pin what it must see and what it must not.
"""
import importlib.util
import json
import subprocess
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude/hooks/require_sweep_before_catalogue.py"
_spec = importlib.util.spec_from_file_location("require_sweep", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_CLASS = "+## a-brand-new-class\n+- status: guarded\n"
_RECUR = "+  - 2026-09-25 (récidive): a new site\n"


def _tool_use(tool: str, **inp) -> str:
    return json.dumps({"message": {"content": [{"type": "tool_use", "name": tool, "input": inp}]}})


def _transcripts(tmp_path: Path, *lines: str) -> Path:
    d = tmp_path / "projects" / "sub"
    d.mkdir(parents=True)
    (d / "s.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path / "projects"


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    """A class added with no sweeper call anywhere is refused; with a real call, allowed."""
    none = hook.proof(_transcripts(tmp_path, _tool_use("Agent", subagent_type="code-critic")))
    assert hook.verdict(hook.added_entries(_CLASS), none) is not None
    assert hook.verdict(hook.added_entries(_CLASS), {"sibling-sweeper"}) is None


def test_a_sentence_that_names_the_agent_is_not_a_call(tmp_path) -> None:
    cited = json.dumps({"message": {"content": [
        {"type": "text", "text": "Spawn sibling-sweeper before the fix"}]}})
    assert hook.proof(_transcripts(tmp_path, cited)) == set()


def test_a_real_call_in_a_subagent_transcript_counts(tmp_path) -> None:
    """Workflow sub-agents write under <session>/subagents/…; the search is recursive."""
    root = _transcripts(tmp_path, _tool_use("Agent", subagent_type="sibling-sweeper"))
    assert hook.proof(root) == {"sibling-sweeper"}


def test_two_entries_need_the_engineering_loop(tmp_path) -> None:
    two = hook.added_entries(_CLASS + _RECUR)
    assert two == 2
    assert hook.verdict(two, {"sibling-sweeper"}) is not None
    loop = hook.proof(_transcripts(tmp_path, _tool_use("Workflow", name="engineering-loop")))
    assert hook.verdict(two, loop) is None


def test_an_old_sweep_does_not_count(tmp_path) -> None:
    root = _transcripts(tmp_path, _tool_use("Agent", subagent_type="sibling-sweeper"))
    assert hook.proof(root, now=(root / "sub" / "s.jsonl").stat().st_mtime + 49 * 3600) == set()


def test_only_a_git_commit_is_inspected() -> None:
    assert hook.is_git_commit("git add -A && git commit -q -m x")
    assert hook.is_git_commit("cd /r && git -C /r commit -m x")
    assert not hook.is_git_commit('echo "git commit is what we do next"')
    assert not hook.is_git_commit("git log --grep commit")


def test_the_hook_blocks_end_to_end(tmp_path) -> None:
    """Real git repo, real hook process: blocked, then allowed once a sweep is on record."""
    repo = tmp_path / "repo"
    cat = repo / ".claude/dev-docs/error-classes.md"
    cat.parent.mkdir(parents=True)
    cat.write_text("# catalogue\n", encoding="utf-8")
    for cmd in (["init", "-q"], ["add", "-A"],
                ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True)
    cat.write_text("# catalogue\n\n## a-brand-new-class\n- status: guarded\n", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    payload = json.dumps({"tool_input": {"command": "git add -A && git commit -m x"},
                          "cwd": str(repo)})

    def run(transcripts: Path) -> int:
        return subprocess.run(["python3", str(_HOOK)], input=payload, text=True,
                              capture_output=True, timeout=30,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                                   "HOOK_TRANSCRIPTS_DIR": str(transcripts)}).returncode

    assert run(empty) == 2
    assert run(_transcripts(tmp_path, _tool_use("Agent", subagent_type="sibling-sweeper"))) == 0
