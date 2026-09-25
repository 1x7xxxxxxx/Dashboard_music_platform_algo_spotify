"""The Stop hook proposes, for the roadmap, the actions this session declared and did not write.

Type: Sub
Uses: .claude/hooks/draft_roadmap.py
Depends on: git (a throwaway repo), fabricated engineering-loop journals

Advisory by design (code-critic, 2026-09-25): it cannot see an action written nowhere,
so it never blocks. These tests pin what it must propose and what it must not.
"""
import importlib.util
import subprocess
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude/hooks/draft_roadmap.py"
_spec = importlib.util.spec_from_file_location("draft_roadmap", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _repo(tmp_path: Path, message: str) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    (r / "f").write_text("x")
    for cmd in (["init", "-q"], ["add", "-A"],
                ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", message]):
        subprocess.run(["git", "-C", str(r), *cmd], check=True)
    return r


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    """A commit that declares an open action the checklist lacks -> proposed; once written -> not."""
    repo = _repo(tmp_path, "fix X\n\nOuvert : relancer la sonde de nuit après le dimanche\n")
    found = hook.commit_actions(repo, since=0)
    assert found == ["relancer la sonde de nuit après le dimanche"]
    assert hook.missing(found, "## 📋 Tâches ouvertes\n| R1 | autre chose |\n") == found
    assert hook.missing(found, "| R9 | relancer la sonde de nuit après le dimanche |") == []


def test_a_commit_without_open_lines_proposes_nothing(tmp_path) -> None:
    repo = _repo(tmp_path, "fix Y\n\nRien ne reste ouvert ici.\n")
    assert hook.commit_actions(repo, since=0) == []
