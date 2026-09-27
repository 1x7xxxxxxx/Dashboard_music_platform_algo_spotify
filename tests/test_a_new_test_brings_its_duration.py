"""R250 — the commit that adds a test brings its duration (main went red on it 3× on 2026-09-27)."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _hook() -> dict | None:
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return next((h for repo in cfg["repos"] for h in repo.get("hooks", [])
                 if h.get("id") == "test-durations-known"), None)


def test_the_commit_hook_checks_the_durations_of_staged_tests():
    hook = _hook()
    assert hook, "the pre-commit hook test-durations-known is gone"
    assert "check_durations_are_collectable.py" in hook["entry"]
    assert "--fix" not in hook["entry"], "a commit hook must refuse, not rewrite the suite"
    pattern = re.compile(hook["files"])
    assert pattern.search("tests/test_new_guard.py"), "a new test file would not trigger it"
    assert not pattern.search("src/dashboard/app.py")
