#!/usr/bin/env python3
"""Record the defect SYMPTOMS of each turn — the trace of defects that never become a class.

Type: Utility
Triggers: called by the Stop hook `.claude/hooks/session_summary.py`, once per assistant reply
Uses: the session transcript (JSONL) named in the hook's stdin
Persists in: `.claude/sessions/defects.jsonl` (append-only, gitignored — the repo is public)
             `.claude/sessions/.defects-offset-<session>` (byte offset already read)

R315 (2026-09-29). Rule 15 sends ~7 defects in 8 to a test, not to a class; until now their
only trace was a commit message. This module keeps the SYMPTOM, not a judgement: a red test
node, a traceback (exception type + innermost repo file), a hook or pre-commit refusal.
`tools/dev/defect_log.py` (`make defect-log`) reconciles them afterwards.

Deliberately NOT recorded (code-critic, R315): a non-zero Bash exit. `grep` with no match
exits 1, `diff` exits 1 on a difference — control flow, not a defect — and it would drown the
three high-precision signals. Permission denials are the user's choice, not a defect.

The transcript is read from the offset left by the previous call, so the cost is the size of
ONE turn, never of the whole session (a /loop night would otherwise go quadratic).

---
rex: []
---
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / ".claude" / "sessions" / "defects.jsonl"
EXCERPT = 200
FIRST_READ_MAX = 2_000_000  # bytes read on the first Stop of a session

_FAILED = re.compile(r"^(?:FAILED|ERROR) (tests/[^\s:]+\.py::\S+)", re.M)
_GREEN = re.compile(r"^=*\s*(\d+) passed(?:,| in)(?![^\n]*\bfailed\b)(?![^\n]*\berror)", re.M)
_FULL_SUITE = re.compile(r"\bmake test(?:-fast)?(?![\w-])")
_TEST_FILE = re.compile(r"\btests/[\w/.-]+\.py\b")
_CHANGED = re.compile(r"\bmake test-changed\b")
SELECTED = ROOT / ".pytest-selected"   # written by `make test-changed` (R321)
_TRACEBACK = "Traceback (most recent call last):"
_FRAME = re.compile(r'^\s*File "([^"]+)", line \d+', re.M)
_EXC = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt))\b", re.M)
_HOOK = re.compile(r"(?:PreToolUse|PostToolUse|Stop):?\w*:? hook error.*?\.claude/hooks/(\w+)\.py", re.S)
_COMMITS = re.compile(r"\bgit\b[^|;&]*\bcommit\b|\bpre-commit\s+run\b")
_UNSAFE = re.compile(r"[^\w-]")
_PRECOMMIT = re.compile(r"^(?![AMDR?]{1,2} )(\S.*?)\.{3,}(?:\([^)]*\))?Failed$", re.M)
_CODE = re.compile(r"`[^`]*`")

_REDACT = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    # a secret mixes cases AND digits; a test name or a commit sha does not
    (re.compile(r"\b(?=[\w-]*[a-z])(?=[\w-]*[A-Z])(?=[\w-]*\d)[\w-]{24,}\b"), "<redacted>"),
    (re.compile(r"\b(?:ghp|gho|ghs|github_pat|sk|xox[bp])[_-][\w-]{16,}"), "<redacted>"),
    (re.compile(r"/home/[^/\s]+/"), "~/"),
)


def redact(text: str) -> str:
    """What may be written next to the repo: no e-mail, no token, no home path. Pure."""
    text = text.replace(str(ROOT) + "/", "")
    for pattern, repl in _REDACT:
        text = pattern.sub(repl, text)
    return text[:EXCERPT]


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _repo_file(path: str) -> str | None:
    try:
        rel = Path(path).resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return None
    return None if rel.startswith((".venv/", "venv/", "<")) else rel


def _traceback_symptom(text: str) -> tuple[str, str] | None:
    tail = text[text.rfind(_TRACEBACK):]
    frames = [f for f in (_repo_file(p) for p in _FRAME.findall(tail)) if f]
    exc = _EXC.findall(tail)
    if not exc:
        return None
    if not frames:  # a throwaway `python3 -` script: not the repo's defect
        return None
    where = frames[-1]
    return f"traceback:{exc[-1].rsplit('.', 1)[-1]}@{where}", exc[-1]


def symptoms(text: str, command: str = "", selected: "list[str] | None" = None) -> list[dict]:
    """The symptoms one tool result shows. Pure: the heart of what is recorded."""
    out = [{"kind": "test_red", "fingerprint": f"test:{node}", "excerpt": node}
           for node in dict.fromkeys(_FAILED.findall(text))]
    if _TRACEBACK in text and not out:
        found = _traceback_symptom(text)
        if found:
            out.append({"kind": "traceback", "fingerprint": found[0], "excerpt": found[1]})
    hook = _HOOK.search(text)
    if hook:
        reason = next((ln.split(":", 1)[-1] for ln in text.splitlines()
                       if ln.strip().startswith("Reason")), "")
        gist = " ".join(_CODE.sub("", reason).lower().split()[:6])
        out.append({"kind": "hook_refusal", "fingerprint": f"hook:{hook.group(1)}:{gist}",
                    "excerpt": reason.strip() or hook.group(1)})
    # R318: only a COMMIT's refusal is one. The same lines shown again by `grep`/`tail` on a
    # log are a reading, and counted 23 end-of-file refusals where 3 happened (2026-09-29).
    for name in dict.fromkeys(_PRECOMMIT.findall(text) if _COMMITS.search(command) else ()):
        out.append({"kind": "precommit_refusal", "fingerprint": f"precommit:{name.strip()}",
                    "excerpt": name.strip()})
    if not out and _GREEN.search(text):
        files = sorted(set(_TEST_FILE.findall(command)))
        # a green only proves the nodes it ran: named files, or the WHOLE suite. A diff-
        # selected run (`make test-changed`) names neither in its command — R321 (2026-09-29):
        # it writes its selection to `.pytest-selected`, handed in here as `selected`.
        if not files and selected and _CHANGED.search(command):
            files = sorted(set(selected))
        scope = "files" if files else "suite" if _FULL_SUITE.search(command) else "unknown"
        out.append({"kind": "test_green", "fingerprint": "green", "scope": scope,
                    "excerpt": " ".join(files) or f"({scope})", "files": files})
    return out


def events_of_lines(lines: list[str], session: str,
                    selected: "list[str] | None" = None) -> list[dict]:
    """Symptom events from transcript lines (tool_use commands joined to their results)."""
    commands: dict[str, str] = {}
    events = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use":
                commands[item.get("id", "")] = str((item.get("input") or {}).get("command", ""))
            elif item.get("type") == "tool_result":
                cmd = commands.get(item.get("tool_use_id", ""), "")
                for s in symptoms(_text_of(item.get("content")), cmd, selected):
                    s["excerpt"] = redact(s["excerpt"])
                    s["fingerprint"] = redact(s["fingerprint"])
                    s.update(ts=entry.get("timestamp", ""), session=session, status="observed")
                    events.append(s)
    return events


def fresh_selection(path: Path = SELECTED, max_age_s: float = 3600) -> "list[str] | None":
    """The last `make test-changed` selection, if recent enough to be this turn's run."""
    try:
        if time.time() - path.stat().st_mtime > max_age_s:
            return None
        return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")]
    except OSError:
        return None


def capture(transcript_path: str, session: str, log: Path = LOG,
            backfill: bool = False) -> int:
    """Append the symptoms written since the last call; returns how many."""
    src = Path(transcript_path)
    if not transcript_path or not src.is_file():
        return 0
    safe = _UNSAFE.sub("", session) or "x"
    marker = log.parent / f".defects-offset-{safe}"
    size = src.stat().st_size
    try:
        start = 0 if backfill else int(marker.read_text())  # duplicates: deduped by the log
    except (OSError, ValueError):
        # First call on a session. A session resumed long after it started would cost
        # seconds to read whole on one Stop: start at its end, `--backfill` catches up.
        start = 0 if backfill or size <= FIRST_READ_MAX else size
    if start > size:
        start = 0
    with src.open("rb") as f:
        f.seek(start)
        chunk = f.read()
    end = start + chunk.rfind(b"\n") + 1  # a half-written last line is read next time
    lines = chunk[: end - start].decode("utf-8", errors="replace").splitlines()
    # backfill replays old turns: today's selection would be pinned on them — none then.
    events = events_of_lines(lines, session, None if backfill else fresh_selection())
    log.parent.mkdir(parents=True, exist_ok=True)
    if events:
        stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        with log.open("a", encoding="utf-8") as out:
            for e in events:
                e["ts"] = e["ts"] or stamp
                out.write(json.dumps(e, ensure_ascii=False) + "\n")
    marker.write_text(str(end))
    return len(events)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3 or not sys.argv[1] == "--backfill":
        sys.exit("usage: defect_capture.py --backfill <transcript.jsonl>")
    path = Path(sys.argv[2])
    print(f"{capture(str(path), path.stem, backfill=True)} symptom(s) recorded in {LOG}")
