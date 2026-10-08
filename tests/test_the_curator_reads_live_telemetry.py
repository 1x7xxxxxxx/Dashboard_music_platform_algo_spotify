"""R470 — the curator's telemetry is read from live sources and says when a source froze.

Type: Test
Uses: .claude/scripts/curator.py
Depends on: nothing live — synthetic usage_report data and a tmp `.claude` root
Persists in: nothing

Until 2026-10-08 the weekly config review printed « audit-collectors: 6× · last
2026-06-19 » as current: its skills counter (usage.json) had died on 2026-07-28, and its
lifecycle pass globbed `skills/*.md`, which since the move to directories matches only the
`*.rex.md` side files — it judged no skill at all. What must hold:
1. skills are counted from transcript `Skill` calls AND `skills/<name>/` injections;
2. a source whose newest record is older than _FROZEN_DAYS says it is frozen;
3. the lifecycle pass reads `skills/<name>/SKILL.md` and flags an unused old one.

Mutation record (2026-10-08): seen red with the injection branch removed from
skill_activity, with the `age > _FROZEN_DAYS` test inverted, and with the lifecycle glob
put back to `*.md`.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))

import curator  # noqa: E402

_DATA = {
    "skills": {"capitalise": 2},
    "last_seen": {"skill:capitalise": "2026-09-28T10:00:00.000Z"},
    "injections": {"found": True,
                   "counts": {"skills/db-schema/SKILL.md": 3, "workflows/bug-resolution.md": 9},
                   "last_seen": {"skills/db-schema/SKILL.md": "2026-10-08T09:00:00+00:00"}},
}


def test_skills_are_counted_from_calls_and_injections() -> None:
    acts = curator.skill_activity(_DATA)
    assert acts["capitalise"] == {"invoked": 2, "injected": 0, "last": "2026-09-28"}
    assert acts["db-schema"] == {"invoked": 0, "injected": 3, "last": "2026-10-08"}
    assert "bug-resolution" not in acts and "workflows" not in acts


def test_a_source_that_stood_still_says_so() -> None:
    today = datetime(2026, 10, 8, tzinfo=timezone.utc)
    assert "frozen since 2026-09-27" in curator.freshness("2026-09-27", today)
    assert "frozen" not in curator.freshness("2026-10-06", today)
    assert "never" in curator.freshness("", today)


def test_the_report_dates_each_section() -> None:
    lines, usage = curator._telemetry(ROOT / ".claude", transcripts=_DATA)
    text = "\n".join(lines)
    assert "db-schema: 0 invoked · 3 injected" in text
    assert text.count("last record") + text.count("frozen since") + text.count("no usage.json") \
        + text.count("unreadable") >= 2, text
    assert usage["skill_activity"]["db-schema"]["injected"] == 3


def test_the_lifecycle_judges_skill_directories(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "ghost" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\n---\n", encoding="utf-8")
    (tmp_path / "skills" / "ghost.rex.md").write_text("rex: []\n", encoding="utf-8")
    old = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(skill, (old, old))
    lines = curator._lifecycle(tmp_path, {"skill_activity": {}}, stale_days=30)
    assert any(ln.startswith("- ghost (never invoked") for ln in lines), lines
    used = curator._lifecycle(
        tmp_path, {"skill_activity": {"ghost": {"invoked": 1, "injected": 0,
                                                "last": datetime.now(timezone.utc).strftime("%Y-%m-%d")}}},
        stale_days=30)
    assert not any("ghost" in ln for ln in used), used
