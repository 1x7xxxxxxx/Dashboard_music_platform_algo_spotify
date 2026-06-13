#!/usr/bin/env python3
"""
Best-effort usage telemetry for the Claude Code config self-improvement loop.

`record(category, key, hit=None)` increments counters in the gitignored sidecar
`.claude/curator/usage.json`, so `/curator` can later see what actually fires
(which skills get injected, which error-class signatures run / hit) and flag the
rest as stale. NEVER raises — telemetry must not break a hook or a CI sweep; any
failure is swallowed silently. Callers import it defensively (try/except).

Schema (usage.json):
  {"schema": 1,
   "skills":        {"<name>": {"count": N, "last": "YYYY-MM-DD"}},
   "error_classes": {"<id>":   {"count": N, "runs": N, "hits": N, "last": "…"}}}

Type: Utility (Claude Code config)
Uses: json, .claude/curator/usage.json
Persists in: .claude/curator/usage.json (gitignored)

---
rex: []
---
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def usage_path() -> Path:
    # .claude/scripts/ -> repo root -> .claude/curator/usage.json
    root = Path(__file__).resolve().parents[2]
    return root / ".claude" / "curator" / "usage.json"


def record(category: str, key: str, hit: bool | None = None) -> None:
    """Increment the counter for (category, key). Best-effort, never raises."""
    try:
        p = usage_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("schema", 1)
        rec = data.setdefault(category, {}).setdefault(key, {})
        rec["count"] = int(rec.get("count", 0)) + 1
        if hit is not None:
            rec["runs"] = int(rec.get("runs", 0)) + 1
            if hit:
                rec["hits"] = int(rec.get("hits", 0)) + 1
        rec["last"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, p)
    except Exception:
        # Telemetry is strictly best-effort; a broken sidecar must never break
        # the calling hook / sweep. Intentionally swallow everything.
        pass
