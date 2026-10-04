"""R353 — every red the defect log records can close, each by the proof that fits its kind.

Type: Test
Uses: tools/dev/defect_log.py, tools/dev/import_cron_logs.py, .claude/hooks/session_start.py
Depends on: nothing live — synthetic events
Persists in: nothing

Before R353 only a `test:` red could ever close: a traceback, a CI gate red or a cron failure
stayed `open` forever, so `open` meant nothing — and nothing read the log at a session start.
What must hold:
1. a `ci-step` closes on a later CI green, not on a session's green;
2. a `cron` failure closes on the SAME step's later `rc=0`, not on another step of its run;
3. a traceback is `fixed` only when its file was committed after it AND CI went green after
   that commit;
4. a manual close needs a reason and a known fingerprint, and a red after it reopens;
5. a cron line is read as `<ts> … <step> rc=<N>`, in UTC, redacted, within the window;
6. the session-start banner never raises.

Mutation record (2026-10-04): seen red on a `ci-step` closed by any green, a cron closed by
any step's `rc=0`, `closed`/`fixed` never returned, the cron step forced to `run`, the age
window removed. Written test-first, it caught two live defects: a traceback `fixed` by a
commit made BEFORE it, and a cron recovery classed `transient`.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
sys.path.insert(0, str(ROOT / "tools" / "dev"))
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

import defect_log as dl  # noqa: E402
import import_cron_logs as cron  # noqa: E402
import session_start  # noqa: E402

T0 = "2026-10-01T10:00:00.000+00:00"
T1 = "2026-10-01T11:00:00.000+00:00"
T2 = "2026-10-01T12:00:00.000+00:00"
T3 = "2026-10-01T13:00:00.000+00:00"


def _ev(kind: str, fp: str, ts: str, session: str = "s1", **kw) -> dict:
    return {"kind": kind, "fingerprint": fp, "ts": ts, "session": session,
            "excerpt": fp, **kw}


def _green(ts: str, session: str) -> dict:
    return _ev("test_green", "green", ts, session, scope="suite", files=[])


def _status(events: list[dict], fp: str, touched: dict | None = None) -> str:
    return next(r["status"] for r in dl.classify(events, touched) if r["fingerprint"] == fp)


def test_a_ci_step_closes_on_ci_green_only() -> None:
    red = _ev("ci_step", "ci-step:Gates/ruff", T0, "ci:1")
    assert _status([red, _green(T1, "local-session")], red["fingerprint"]) == "open"
    assert _status([red, _green(T1, "ci:2")], red["fingerprint"]) == "green"


def test_a_cron_failure_closes_on_its_own_step_only() -> None:
    red = _ev("cron_red", "cron:rag:ingest", T0, "cron:rag")
    other = _ev("cron_ok", "cron:rag:labels", T1, "cron:rag")
    same = _ev("cron_ok", "cron:rag:ingest", T2, "cron:rag")
    assert _status([red, other, _green(T1, "ci:2")], "cron:rag:ingest") == "open"
    assert _status([red, other, same], "cron:rag:ingest") == "green"


def test_a_traceback_is_fixed_by_a_commit_then_a_ci_green() -> None:
    fp = "traceback:KeyError@tools/x.py"
    red, ci = _ev("traceback", fp, T1), _green(T3, "ci:9")
    assert _status([red, ci], fp, {}) == "open"                          # file never committed
    assert _status([red, ci], fp, {"tools/x.py": T0}) == "open"          # commit BEFORE the red
    assert _status([red, _green(T1, "ci:8")], fp, {"tools/x.py": T2}) == "open"  # CI before it
    assert _status([red, ci], fp, {"tools/x.py": T2}) == "fixed"
    assert _status([red, _green(T3, "s2")], fp, {"tools/x.py": T2}) == "open"  # not CI


def test_a_manual_close_needs_a_reason_and_a_red_reopens_it(tmp_path, capsys) -> None:
    log = tmp_path / "defects.jsonl"
    fp = "traceback:KeyError@stdin.py"
    log.write_text(json.dumps(_ev("traceback", fp, T0)) + "\n")
    assert dl.close(fp, "  ", log) == 1
    assert dl.close("traceback:Nope@x.py", "why", log) == 1
    assert dl.close(fp, "script <stdin> jetable, pas le dépôt", log) == 0
    events = dl.load(log)
    assert _status(events, fp) == "closed"
    later = _ev("traceback", fp, datetime.now(timezone.utc).replace(year=2099).isoformat())
    assert _status(events + [later], fp) == "open"


def test_a_cron_line_is_read_by_step_in_utc_redacted_within_the_window() -> None:
    text = ("2026-10-04T11:46:41+02:00 ingest rc=3\n"
            "2026-10-04T11:46:42+02:00 notify rc=0 to someone@example.com\n"
            "   ingest rc=9 (no timestamp: a continuation line)\n"
            "2026-08-01T00:00:00+02:00 ingest rc=1\n"
            "2026-10-04T16:17:06+02:00 === fin (rc=0) ===\n"
            "2026-10-04T16:18:00+02:00 rc=2\n")
    got = cron.events_of("job", text, datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert [(e["kind"], e["fingerprint"]) for e in got] == [
        ("cron_red", "cron:job:ingest"), ("cron_ok", "cron:job:notify"),
        ("cron_ok", "cron:job:fin"), ("cron_red", "cron:job:run")]
    assert got[0]["ts"] == "2026-10-04T09:46:41.000+00:00"
    assert "@" not in got[1]["excerpt"]


def test_the_summary_counts_open_defects_by_kind() -> None:
    events = [_ev("cron_red", "cron:a:x", T0), _ev("traceback", "traceback:E@f.py", T0)]
    line = dl.summary(dl.classify(events, {}))
    assert line.startswith("2 défaut(s) ouvert(s) (1 cron_red, 1 traceback)")


def test_the_session_banner_never_raises(tmp_path, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise ValueError("corrupt")
    monkeypatch.setattr(dl, "load", boom)
    monkeypatch.setattr(cron, "main", lambda: 0)
    assert "illisible" in session_start.defect_banner(ROOT)
