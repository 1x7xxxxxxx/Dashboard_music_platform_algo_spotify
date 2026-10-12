#!/usr/bin/env python3
"""Stop hook — code changed after the last test verdict blocks the end of turn ONCE (R549).

Type: Hook
Uses: _verdict.verdict (the same definition the statusline reads), _hook_trace
Triggers: Stop, registered in .claude/settings.json
Persists in: <trace dir>/stop-gate.jsonl — one line per block: the review of 2026-10-26
             (`tools/dev/reopen_check.py::_mods_review`) counts them

Why: an agent says « résolu » because it modified code, not because a verdict says so.
A mod cannot do this — `turn.complete` only observes; a Stop hook can refuse the stop.

Blocks ONCE per edit: `stop_hook_active` lets the continued turn stop, and an edit
already blocked on is not blocked again — the answer « je ne lance pas les tests,
parce que… » is a legitimate end of turn. Exits 0 on any error: a broken gate must
never trap a session.

---
rex: []
---
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_trace import trace as _trace, trace_dir  # noqa: E402
from _verdict import _git, verdict  # noqa: E402

_trace(__file__)

REASON = ("du code a changé après le dernier verdict de tests ({file}) — lance "
          "`make test-changed`, ou dis explicitement pourquoi tu ne le lances pas. "
          "Ne dis pas « résolu » sur une modification non vérifiée.")


def _already_blocked(log: Path | None, stamp: float) -> bool:
    if log is None or not log.exists():
        return False
    lines = log.read_text(errors="replace").splitlines()
    return bool(lines) and json.loads(lines[-1]).get("last_edit") == stamp


def decide(root: Path, payload: dict, log: Path | None) -> dict | None:
    """The block decision, or None to let the turn end."""
    if payload.get("stop_hook_active"):
        return None
    v = verdict(root)
    if v.state not in ("absent", "périmé") or v.last_edit is None:
        return None
    if _already_blocked(log, v.last_edit):
        return None
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "state": v.state, "file": v.edited_file, "last_edit": v.last_edit}) + "\n")
    return {"decision": "block", "reason": REASON.format(file=v.edited_file)}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        root = Path(payload.get("cwd") or ".").resolve()
        top = _git(root, "rev-parse", "--show-toplevel")
        if not top:
            return 0
        d = trace_dir()
        out = decide(Path(top[0]), payload, d / "stop-gate.jsonl" if d else None)
    except Exception:  # noqa: BLE001 — a broken gate must never trap a session
        return 0
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
