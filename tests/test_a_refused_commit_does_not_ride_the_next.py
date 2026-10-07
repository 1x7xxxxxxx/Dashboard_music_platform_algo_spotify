"""R452 — a refused commit does not leave its index to the next commit of the same line.

Type: Test
Uses: .claude/hooks/guard_destructive (_commit_riding_a_refused_one, check_command)
Depends on: .claude/hooks/guard_destructive.py
Persists in: nothing

On 2026-10-07 the durations hook refused « R448 : … »; its output was piped into `grep`,
a `;` followed, and the next `git add … && git commit -qm "R449 : …"` carried R448's
staged files under R449's id. A pre-commit refusal keeps the index — the next commit
takes it. The property guarded: a second commit is reached only by a `&&` chain from
the first.

Sweep (rule 20, 2026-10-07) over every Bash command of this project's transcripts:
147 contain « git commit » twice → 48 pass (`&&` chain, or the second one is heredoc
text) → 1 false positive excluded (a `--dry-run` probe, now exempt) → 98 blocked, real
second commits reached by `;` or a newline — mostly « retry after the durations
refusal », harmless under the same message, and R448 / R278 where the id changed.

Mutation record: `op != "&&"` → `False` → red (8 riding cases) ; the `--dry-run`
exemption removed → red (the probe case).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard_destructive.py"


def _hook():
    spec = importlib.util.spec_from_file_location("_guard_destructive_r452", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R448 = ('git add .test_durations .github/workflows/ci.yml && git commit -qm "R448 : x\n\n'
        'Co-Authored-By: C <n@a.com>" 2>&1 | grep -E "Failed|❌"; git add tools/dev/night_run.py '
        '&& git commit -qm "R449 : y"')

_RIDING = [
    R448,
    "git commit -m a; git commit -m b",
    "git commit -m a | tail -1; git add f && git commit -m b",
    "git commit -m a\ngit commit -m b",
    "git commit -m a || true; git commit -m b",
    "git commit -m a && git push; git commit -m b",
    "rtk git -C /repo commit -m a; git commit -m b",
    "git commit -m a && git commit -m b; git commit -m c",
]

_SAFE = [
    "git commit -m a && git commit -m b",
    "git add f && git commit -m a && git add g && git commit -m b",
    'git commit -m a 2>&1 | grep -E "Failed"',
    "git commit -q -F - > ~/.cache/commit.log 2>&1 <<'EOF'\nR1 : x\n\ngit commit -m inside\nEOF\necho rc=$?",
    'git commit -m "first line\n\nCo-Authored-By: C <n@a.com>" > f 2>&1; echo rc=$?',
    'echo "git commit -m a; git commit -m b is the trap"',
    "git log --oneline -1; git commit -m a",
    'git commit -m "probe" --dry-run >/dev/null 2>&1; git commit -m a | tail -1',
]


@pytest.mark.parametrize("command", _RIDING)
def test_a_second_commit_not_guarded_by_the_first_is_blocked(command: str) -> None:
    assert _hook()._commit_riding_a_refused_one(command) is not None, command


@pytest.mark.parametrize("command", _SAFE)
def test_a_guarded_chain_or_a_single_commit_passes(command: str) -> None:
    assert _hook()._commit_riding_a_refused_one(command) is None, command


def test_the_r448_line_is_blocked_by_the_hook_entry_point_with_the_safe_form() -> None:
    verdict = _hook().check_command(R448)
    assert verdict is not None
    level, message = verdict
    assert level == "block" and "echo rc=$?" in message and "R448" in message
