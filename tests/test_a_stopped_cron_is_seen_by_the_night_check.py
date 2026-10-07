"""`make night-check` says when a scheduled GitHub workflow has stopped running (R415).

Type: Sub
Uses: tools/dev/night_run.py (`cron_period_hours`, `scheduled_workflows`, `stale_schedules`)
Depends on: .github/workflows/ (read only) — the run dates are fabricated
Persists in: nothing

A cron that stops (workflow disabled after 60 days without activity, a schedule lost in a
merge) fails by silence: no red run, no mail. R407's neighbour: `gh run list` lagged a
month on 2026-10-05 while the per-workflow API was current, so the dates come from there.

Mutations (2026-10-05): threshold `2 * period` → `20 * period` → RED; a workflow with no
scheduled run skipped instead of reported → RED; `hour.isdigit()` daily case returning
None → RED (a daily workflow silently unmeasured).
Not covered: a workflow whose runs all FAIL (that is `red_main`'s question, main's CI),
and cron lists or ranges (`1,13 * * *`), whose period this check does not compute.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_run_r415", ROOT / "tools/dev/night_run.py")
night_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night_run)

NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


def test_the_period_of_each_cron_shape() -> None:
    p = night_run.cron_period_hours
    assert (p("17 6 * * *"), p("0 * * * *"), p("0 */6 * * *")) == (24.0, 1.0, 6.0)
    assert (p("0 3 * * 1"), p("0 3 1 * *")) == (168.0, 744.0)
    assert p("0 1,13 * * *") is None and p("nonsense") is None


def test_a_run_older_than_two_periods_is_named_and_a_recent_one_is_not() -> None:
    periods = {"daily.yml": 24.0, "fresh.yml": 24.0, "never.yml": 24.0, "unmeasured.yml": 24.0}
    last = {"daily.yml": "2026-10-03T19:00:00Z",   # 49 h
            "fresh.yml": "2026-10-03T21:00:00Z",   # 47 h — GitHub starts crons hours late
            "never.yml": None}
    said = night_run.stale_schedules(periods, last, NOW)
    assert len(said) == 2, said
    assert "daily.yml" in said[0] and "49 h" in said[0]
    assert "never.yml" in said[1]
    assert not any("fresh.yml" in s or "unmeasured.yml" in s for s in said)


def test_every_scheduled_workflow_of_this_repo_is_measured() -> None:
    """A `schedule:` this parser cannot read would leave its cron unwatched, in silence."""
    scheduled = {wf.name for wf in (ROOT / ".github" / "workflows").glob("*.y*ml")
                 if "schedule:" in wf.read_text(encoding="utf-8")}
    assert scheduled, "no scheduled workflow found — the check is vacuous"
    assert set(night_run.scheduled_workflows()) == scheduled


def test_a_cron_born_today_is_not_a_stopped_cron() -> None:
    """R451 — 2026-10-07: `ci.yml` got its schedule at 16:30 and night-check said « le cron
    ne tourne pas » the same evening. With no scheduled run, age counts from the commit."""
    periods, last = {"ci.yml": 24.0}, {"ci.yml": None}
    assert night_run.stale_schedules(periods, last, NOW, {"ci.yml": "2026-10-05T09:00:00+02:00"}) == []
    old = night_run.stale_schedules(periods, last, NOW, {"ci.yml": "2026-10-01T09:00:00+02:00"})
    assert len(old) == 1 and "aucun run planifié" in old[0]
    assert len(night_run.stale_schedules(periods, last, NOW, {})) == 1, "unknown birth stays loud"
