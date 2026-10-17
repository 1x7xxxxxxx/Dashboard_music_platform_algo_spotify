"""REQ-HARN-30 — the roadmap auto-commit hook (copied from the baseline, T21/T25) pushes only at 0.

guard_scope: the push decision of .claude/hooks/roadmap_autocommit.py. NOT covered: the commit
and the detached push, tested against a real repo in the baseline (tools/dev/test_roadmap_autocommit.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))
import roadmap_autocommit as a  # noqa: E402


def test_the_push_waits_for_an_empty_index_and_never_retries_a_refused_head() -> None:
    assert a.decide_push(0, 0, 1, head="h1"), "index at 0, one commit ahead"
    assert not a.decide_push(0, 1, 1), "an open task holds the push"
    assert not a.decide_push(0, 0, 1, pending=True), "one push at a time"
    assert not a.decide_push(0, 0, 1, head="h1", refused="h1"), "a refused HEAD is not retried"
    assert not a.decide_push(0, 0, 1, behind=2), "behind origin: reported, not attempted"
