#!/usr/bin/env python3
"""The project statusline — the « engineering HUD » of a session (R550).

Type: Utility
Uses: _verdict (.claude/hooks/, the same state the Stop gate reads), git, gh (detached)
Triggers: `statusLine` in .claude/settings.json — Claude Code pipes the session JSON on
          stdin at each message (debounced 300 ms)
Persists in: ~/.cache/streamlytics-ci-<sha>.json (the CI of HEAD, refreshed ≤ 1/min)

Two lines:
  1. model · context % · estimated cost · duration · lines +/− (from stdin)
  2. tests (via _verdict) · CI of HEAD · uncommitted files · unpushed commits · night unit

Never a synchronous network call: the CI is read from a cache that a DETACHED
`gh run list --commit <full sha>` refreshes. An unknown CI shows « ? », never ✅ — a
green that was not read is the defect this repo pays most (a full table reads as fresh).
Study: .claude/dev-docs/studies/2026-10-12-mods-claude-code.md (M3).

---
rex: []
---
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from _verdict import Verdict, _git, verdict  # noqa: E402

CACHE = Path.home() / ".cache"
CI_TTL_S = 60
_NIGHT = Path(".claude") / "dev-docs" / "roadmap" / "night-run.jsonl"


@dataclass(frozen=True)
class State:
    tests: Verdict
    ci: str | None = None          # success | failure | running | none | None (unknown)
    sha: str = ""
    dirty: int = 0
    ahead: int | None = None       # None: no upstream
    night: str | None = None


def _duration(ms: float) -> str:
    m = int(ms // 60000)
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m} min"


def _tests(v: Verdict) -> str:
    return {
        "vert": f"✅ {v.passed} verts",
        "rouge": f"❌ {v.failed} rouge(s)",
        "en cours": "⏳ suite en cours",
        "périmé": f"⚠️ périmé ({Path(v.edited_file or '?').name})",
    }.get(v.state, "— aucun verdict")


def _ci(ci: str | None) -> str:
    return {"success": "✅", "failure": "❌", "running": "⏳", "none": "aucun run"}.get(ci, "?")


def render(payload: dict, state: State) -> list[str]:
    cost = payload.get("cost") or {}
    model = (payload.get("model") or {}).get("display_name") or "?"
    ctx = (payload.get("context_window") or {}).get("used_percentage")
    line1 = " · ".join([
        model,
        f"ctx {ctx:.0f} %" if isinstance(ctx, (int, float)) else "ctx ?",
        f"~${cost.get('total_cost_usd', 0):.2f}",
        _duration(cost.get("total_duration_ms", 0)),
        f"+{cost.get('total_lines_added', 0)}/−{cost.get('total_lines_removed', 0)}",
    ])
    parts = [f"tests {_tests(state.tests)}", f"CI {_ci(state.ci)} {state.sha[:8]}".rstrip(),
             f"{state.dirty} non commité(s)",
             f"{state.ahead} non poussé(s)" if state.ahead is not None else "pas d'amont"]
    if state.night:
        parts.append(f"nuit {state.night}")
    return [line1, " · ".join(parts)]


def ci_from_runs(runs: list[dict]) -> str:
    if not runs:
        return "none"
    if any(r.get("conclusion") in ("failure", "cancelled", "timed_out") for r in runs):
        return "failure"
    if any(r.get("status") != "completed" for r in runs):
        return "running"
    return "success"


def _ci_state(root: Path, sha: str) -> str | None:
    """The cached CI of `sha`; triggers a detached refresh when stale and not final."""
    cache = CACHE / f"streamlytics-ci-{sha}.json"
    ci = None
    if cache.exists():
        try:
            ci = ci_from_runs(json.loads(cache.read_text() or "[]"))
        except ValueError:
            ci = None
        if ci in ("success", "failure"):
            return ci
    asked = cache.with_suffix(".asked")  # one refresh per TTL, even when gh fails
    if asked.exists() and time.time() - asked.stat().st_mtime < CI_TTL_S:
        return ci
    tmp = cache.with_suffix(".tmp")
    cmd = (f"gh run list --commit {sha} --json status,conclusion --limit 20 > '{tmp}' "
           f"&& mv '{tmp}' '{cache}'")
    CACHE.mkdir(exist_ok=True)
    asked.touch()
    subprocess.Popen(["sh", "-c", cmd], cwd=root, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ci


def _night(root: Path) -> str | None:
    try:
        lines = (root / _NIGHT).read_text().splitlines()[-20:]
    except OSError:
        return None
    last = json.loads(lines[-1]) if lines else {}
    return last.get("task") if last.get("kind") == "start" else None


def collect(root: Path) -> State:
    sha = (_git(root, "rev-parse", "HEAD") or [""])[0]
    ahead = _git(root, "rev-list", "--count", "@{u}..HEAD")
    return State(tests=verdict(root), ci=_ci_state(root, sha) if sha else None, sha=sha,
                 dirty=len(_git(root, "status", "--porcelain")),
                 ahead=int(ahead[0]) if ahead else None, night=_night(root))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    root = Path((payload.get("workspace") or {}).get("project_dir")
                or payload.get("cwd") or ".").resolve()
    try:
        state = collect(root)
    except Exception:  # noqa: BLE001 — a statusline that crashes shows nothing at all
        state = State(tests=Verdict("absent"))
    print("\n".join(render(payload, state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
