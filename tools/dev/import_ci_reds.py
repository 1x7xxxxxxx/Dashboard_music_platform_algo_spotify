#!/usr/bin/env python3
"""Import the test reds (and greens) of main's finished CI runs into the defect log.

Type: Utility
Uses: `gh run list` / `gh run view --log-failed` (ci.yml on main only)
Triggers: `make defect-log`, before `tools/dev/defect_log.py`
Persists in: .claude/sessions/defects.jsonl (append; `defect_log` dedups)

R337 (2026-09-29). The log only saw reds of Claude sessions, never main's CI — although a CI
run on main is the committed tree par excellence, the one place where a red coming back IS a
recurrence (R336 proposes tickets only for `tree: clean`). Design reviewed by code-critic:
  * `--log-failed` prefixes every line with `job<TAB>step<TAB>timestamp ` — stripped before
    matching, or the importer reads nothing and looks green;
  * a failed run with zero test nodes (the `gates` job, a shard's setup) is SAID, and since
    R353 logged as one `ci-step:<job>/<step>` per failed step, closed by the next CI green;
  * ci.yml only: the random-order nightly is order-dependent, and `clean` would turn its
    flakes into tickets;
  * `ts` = when the run FINISHED (`updatedAt`), in the log's millisecond `Z` format, because
    `defect_log` compares timestamps as strings;
  * no state file: re-importing is idempotent through `defect_log`'s dedup on (fingerprint,
    session, ts, files) — the scan is bounded by age and count instead.
Network failure is fail-soft: the reason is printed, the log is left untouched.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / ".claude" / "sessions" / "defects.jsonl"
MAX_RED_RUNS = 5
MAX_AGE = timedelta(days=30)
_PREFIX = re.compile(r"^[^\t]*\t[^\t]*\t\S+ ")
_NODE = re.compile(r"^(?:FAILED|ERROR) (tests/[^\s:]+\.py::\S+)")


def nodes(log_text: str) -> list[str]:
    """Failed test node ids of a `--log-failed` text, prefix stripped, group suffix cut. Pure."""
    out = []
    for line in log_text.splitlines():
        m = _NODE.match(_PREFIX.sub("", line, count=1))
        if m:
            out.append(m.group(1).split("@")[0])
    return list(dict.fromkeys(out))


def steps(log_text: str) -> list[str]:
    """`job/step` of every failed step of a `--log-failed` text, from the line prefix. Pure.

    R353: a red with no test node (the `gates` job, a shard's setup) was only PRINTED — the
    log never held it, so a gate red for a week counted as nothing."""
    out = []
    for line in log_text.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3 and parts[0].strip() and parts[1].strip():
            out.append(f"{parts[0].strip()}/{parts[1].strip()}")
    return list(dict.fromkeys(out))


def stamp(gh_ts: str) -> str:
    """`2026-09-29T03:57:29Z` → `2026-09-29T03:57:29.000+00:00`, the log's own format. Pure."""
    t = datetime.fromisoformat(gh_ts.replace("Z", "+00:00"))
    return t.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def events_of(run: dict, log_text: str | None) -> tuple[list[dict], str | None]:
    """(events, note) for one finished run. Pure."""
    session, ts = f"ci:{run['databaseId']}", stamp(run["updatedAt"])
    if run["conclusion"] == "success":
        return [{"kind": "test_green", "fingerprint": "green", "scope": "suite", "files": [],
                 "excerpt": "(CI main)", "ts": ts, "session": session, "source": "ci",
                 "status": "observed"}], None
    if run["conclusion"] != "failure":
        return [], None                                  # cancelled / skipped: no verdict
    found = nodes(log_text or "")
    if not found:
        failed = steps(log_text or "")
        note = (f"run {run['databaseId']}: failed, 0 test nodes — "
                f"{len(failed)} step(s) logged as ci-step" if failed else
                f"run {run['databaseId']}: failed, 0 test nodes and no readable step")
        return [{"kind": "ci_step", "fingerprint": f"ci-step:{st}", "excerpt": st, "ts": ts,
                 "session": session, "tree": "clean", "source": "ci", "status": "observed"}
                for st in failed], note
    return [{"kind": "test_red", "fingerprint": f"test:{n}", "excerpt": n, "ts": ts,
             "session": session, "tree": "clean", "source": "ci", "status": "observed"}
            for n in found], None


def new_only(events: list[dict], log: Path) -> list[dict]:
    """Drop what the log already holds — the read-side dedup keeps the verdict right, this
    keeps the FILE from growing by forty runs on every `make defect-log`."""
    try:
        have = {(e.get("session"), e.get("fingerprint"))
                for e in map(json.loads, log.read_text(encoding="utf-8").splitlines())
                if str(e.get("session", "")).startswith("ci:")}
    except (OSError, ValueError):
        have = set()
    return [e for e in events if (e["session"], e["fingerprint"]) not in have]


def _gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[:200])
    return r.stdout


def main() -> int:
    try:
        runs = json.loads(_gh("run", "list", "--workflow", "ci.yml", "--branch", "main",
                              "--status", "completed", "-L", "40",
                              "--json", "databaseId,conclusion,updatedAt"))
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as e:
        print(f"⚠ CI non importée ({type(e).__name__}: {e}) — journal inchangé")
        return 0
    cutoff = datetime.now(timezone.utc) - MAX_AGE
    events, reds = [], 0
    for run in runs:
        if datetime.fromisoformat(run["updatedAt"].replace("Z", "+00:00")) < cutoff:
            continue
        text = None
        if run["conclusion"] == "failure":
            if reds >= MAX_RED_RUNS:
                continue
            reds += 1
            try:
                text = _gh("run", "view", str(run["databaseId"]), "--log-failed")
            except (OSError, subprocess.SubprocessError, RuntimeError) as e:
                print(f"⚠ run {run['databaseId']}: journal illisible ({e})")
                continue
        found, note = events_of(run, text)
        if note:
            print(f"⚠ {note}")
        events += found
    events = new_only(events, LOG)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as out:
        for e in events:
            out.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"CI main : {sum(e['kind'] in ('test_red', 'ci_step') for e in events)} rouge(s), "
          f"{sum(e['kind'] == 'test_green' for e in events)} vert(s) importés (nouveaux seulement)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
