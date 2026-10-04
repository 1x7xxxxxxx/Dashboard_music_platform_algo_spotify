#!/usr/bin/env python3
"""Import the failures of this machine's cron jobs into the defect log.

Type: Utility
Uses: the logs named in .claude/sessions/cron-logs.json — {"<name>": "<path>", …}, local
      only (gitignored: the paths are this machine's, the repo is public)
Triggers: `make defect-log`, before `tools/dev/defect_log.py`
Persists in: .claude/sessions/defects.jsonl (append; redacted like every other excerpt)

R353 (2026-10-04). The log saw Claude's sessions and main's CI, never the jobs that run
while nobody watches: the weekly RAG mail run logged `ingest rc=3` for weeks and nothing
counted it. A line `<ISO-8601 ts> … <step> rc=<N>` is the contract — the one these jobs
already write. N > 0 is a `cron_red` with fingerprint `cron:<name>:<step>`; a later
`<step> rc=0` of the same job is the `cron_ok` that closes it. `<step>` is the first word of
the message: one run writes several steps (`fetch rc=0`, `ingest rc=3`, `labels rc=0`), and
keying on the job alone would let `labels rc=0` close the ingest failure of the same run.
Not seen: a failure that writes no `rc=` (a script killed mid-run) — the absence of a
line is not a line.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSIONS = ROOT / ".claude" / "sessions"
LOG = SESSIONS / "defects.jsonl"
CONFIG = SESSIONS / "cron-logs.json"
MAX_AGE = timedelta(days=30)
_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d|Z)) (.*)$")
_RC = re.compile(r"\brc=(\d+)")
_WORD = re.compile(r"[^\W\d_]+")

sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
from defect_capture import redact  # noqa: E402


def events_of(name: str, text: str, since: datetime) -> list[dict]:
    """Cron events of one log text, newer than `since`. Pure."""
    out = []
    for line in text.splitlines():
        m = _LINE.match(line)
        rc = _RC.search(m.group(2)) if m else None
        if not rc:
            continue
        t = datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).astimezone(timezone.utc)
        if t < since:
            continue
        word = _WORD.search(m.group(2)[:rc.start()])
        step = word.group(0).lower() if word else "run"
        out.append({"kind": "cron_red" if int(rc.group(1)) else "cron_ok",
                    "fingerprint": f"cron:{name}:{step}", "excerpt": redact(m.group(2)),
                    "ts": t.isoformat(timespec="milliseconds"), "session": f"cron:{name}",
                    "tree": "n-a", "source": "cron", "status": "observed"})
    return out


def new_only(events: list[dict], log: Path) -> list[dict]:
    """Drop what the log already holds (a cron log repeats nothing, but it is re-read whole)."""
    try:
        have = {(e.get("fingerprint"), e.get("ts"))
                for e in map(json.loads, log.read_text(encoding="utf-8").splitlines())
                if str(e.get("session", "")).startswith("cron:")}
    except (OSError, ValueError):
        have = set()
    seen, out = set(have), []
    for e in events:
        if (e["fingerprint"], e["ts"]) not in seen:
            seen.add((e["fingerprint"], e["ts"]))
            out.append(e)
    return out


def main() -> int:
    try:
        jobs = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ℹ️  aucun journal de cron déclaré ({CONFIG.relative_to(ROOT)} absent : "
              '{"<nom>": "<chemin du .log>"}) — les tâches planifiées ne sont pas lues')
        return 0
    except ValueError as e:
        print(f"⚠ {CONFIG.relative_to(ROOT)} illisible ({e}) — journal inchangé")
        return 0
    since = datetime.now(timezone.utc) - MAX_AGE
    events = []
    for name, path in jobs.items():
        try:
            events += events_of(name, Path(path).read_text(encoding="utf-8", errors="replace"),
                                since)
        except OSError as e:
            print(f"⚠ cron {name} : journal illisible ({type(e).__name__})")
    events = new_only(events, LOG)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as out:
        for e in events:
            out.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"cron : {sum(e['kind'] == 'cron_red' for e in events)} échec(s), "
          f"{sum(e['kind'] == 'cron_ok' for e in events)} succès importés (nouveaux seulement)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
