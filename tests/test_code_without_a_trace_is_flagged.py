"""Guard: the Stop hook notices code that shipped without a journal entry.

Type: Utility
Uses: importlib, subprocess (a throwaway git repo)
Triggers: pytest
Persists in: nothing

Error class `code-ships-without-a-trace`.

Measured 2026-08-28. `session_summary.check_config_devlog_sync` watched `.claude/rules`,
`tools`, `CLAUDE.md`, `.claude/hooks` and `.claude/skills` — the Claude Code
configuration — and **not `src/` or `airflow/`**. A session that only touched production
code triggered no reminder at all. That is the session whose omission costs most: the
code reaches production and the journal keeps nothing of why.

It also compared `mtime`, which lies in both directions — a `git checkout` resets a date
with nothing changed, and touching `DEVLOG.md` for a comma silences the warning without
journalling anything. `check_code_without_a_trace` reads `git status` instead.

## Why this is tested against a real throwaway repo

A hook is code, and this one exists to fire on a state the working tree is rarely in.
Asserting on the current repo would test whichever state today happens to be in — green
by luck. Each case here builds a git repo, puts it in the exact state, and asks what the
function says. The last case is the one that matters: **the hook must never raise**, so a
non-repo is checked too.
"""
from __future__ import annotations

import importlib.util
import subprocess
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "session_summary.py"


@pytest.fixture(scope="module")
def hook():
    if not HOOK.is_file():
        pytest.skip(f"{HOOK} absent")
    spec = importlib.util.spec_from_file_location("session_summary_under_test", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _repo(tmp_path: Path, *changed: str) -> str:
    """A git repo where `changed` are modified relative to HEAD."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    seeded = set(changed) | {"DEVLOG.md", ".claude/dev-docs/roadmap/checklist.md",
                             "src/keep.py", "airflow/keep.py"}
    for rel in seeded:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    for rel in changed:
        (tmp_path / rel).write_text("changed\n", encoding="utf-8")
    return str(tmp_path)


def test_code_alone_is_flagged(hook, tmp_path):
    """The measured gap: only production code moved, neither doc did."""
    out = hook.check_code_without_a_trace(_repo(tmp_path, "src/collectors/x.py"))
    joined = "\n".join(out)
    assert out, "code changed with no DEVLOG and no roadmap entry must be reported"
    assert "src/collectors/x.py" in joined, joined
    assert "DEVLOG.md" in joined and "checklist.md" in joined, (
        f"both untouched documents must be named, not just one: {joined}")


def test_airflow_counts_as_code(hook, tmp_path):
    """DAGs are bind-mounted in production — editing one IS shipping."""
    out = hook.check_code_without_a_trace(_repo(tmp_path, "airflow/dags/alert_monitor.py"))
    assert out and "airflow/dags/alert_monitor.py" in "\n".join(out)


def test_code_with_both_traces_is_silent(hook, tmp_path):
    """The half that must stay quiet, or the reminder becomes noise and gets ignored."""
    out = hook.check_code_without_a_trace(_repo(
        tmp_path, "src/collectors/x.py", "DEVLOG.md",
        ".claude/dev-docs/roadmap/checklist.md"))
    assert out == [], out


def test_a_partial_trace_still_names_what_is_missing(hook, tmp_path):
    """A DEVLOG entry without a roadmap update is the common half-done case."""
    out = hook.check_code_without_a_trace(_repo(tmp_path, "src/collectors/x.py", "DEVLOG.md"))
    joined = "\n".join(out)
    assert out, "a half-updated session must still be reported"
    assert "checklist.md" in joined and "DEVLOG.md — PAS modifié" not in joined, joined


def test_docs_alone_are_silent(hook, tmp_path):
    """Editing only documentation is not a session that forgot anything."""
    assert hook.check_code_without_a_trace(_repo(tmp_path, "DEVLOG.md")) == []


def test_a_non_repo_returns_empty_instead_of_raising(hook, tmp_path):
    """A Stop hook that crashes at the end of a session gets disabled, not fixed."""
    plain = tmp_path / "not_a_repo"
    plain.mkdir()
    assert hook.check_code_without_a_trace(str(plain)) == []


def test_the_watched_trees_are_the_ones_that_ship(hook):
    """Pin the scope: `src/` and `airflow/` are what reaches production here.

    Without this, narrowing `_CODE_WATCH` to something that never changes would make
    every case above pass on a repo where nothing is ever watched.
    """
    assert set(hook._CODE_WATCH) >= {"src/", "airflow/"}, hook._CODE_WATCH
    assert "DEVLOG.md" in hook._DOC_TRACES
    assert any("checklist.md" in d for d in hook._DOC_TRACES), hook._DOC_TRACES


def test_committed_work_of_the_session_is_seen(hook, tmp_path):
    """Once committed, `git status` is empty — the session's commits must still count.

    Measured 2026-09-25: 13 commits on `.claude/`, `tools/`, `Makefile`, `.github/`, ~9
    actions identified, 0 written to the roadmap, and this hook said nothing: the work was
    committed (invisible to `git status`) and outside `_CODE_WATCH`.
    """
    repo = Path(_repo(tmp_path))
    (repo / ".claude/sessions").mkdir(parents=True, exist_ok=True)
    time.sleep(1.1)                     # the seed commit belongs to BEFORE the session
    (repo / ".claude/sessions/.session-start-ts").write_text(f"{time.time()}\n", encoding="utf-8")
    (repo / "tools/dev").mkdir(parents=True, exist_ok=True)
    (repo / "tools/dev/new_check.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tools/dev/new_check.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "a tool, no roadmap"], cwd=repo, check=True)
    out = "\n".join(hook.check_code_without_a_trace(str(repo)))
    assert "tools/dev/new_check.py" in out and "checklist.md" in out, out


def test_a_forgotten_weekly_curator_is_named(hook, tmp_path):
    """R172: `/curator` « weekly » was a wish nothing checked; the run is now dated."""
    import datetime as dt
    stamp = tmp_path / ".claude/curator/last-run"
    assert hook._check_curator_age(str(tmp_path)) is not None, "never run must be said"
    stamp.parent.mkdir(parents=True)
    stamp.write_text("2026-09-10\n", encoding="utf-8")
    assert "15 j" in hook._check_curator_age(str(tmp_path), today=dt.date(2026, 9, 25))
    assert hook._check_curator_age(str(tmp_path), today=dt.date(2026, 9, 14)) is None
