#!/usr/bin/env python3
"""Replay what the suite really READS against what `make test-changed` would select.

Type: Utility
Uses: tools/dev/select_trace_plugin.py (full suite traced), .claude/scripts/select_tests.py
Triggers: `make select-audit` (opt-in: it runs the whole suite)
Persists in: .claude/dev-docs/select-audit.md is NOT written — the verdict is printed

R338 (2026-09-29), code-critic's blocking condition: the selector is a form detector, so
its misses must be MEASURED against the property — « this test read this file ». For every
tracked, non-test file read by 1 to 20 test modules (more is `git ls-files`-style noise), one
probe per directory: `select(_changed=[file])`, then list the readers not selected.
Exit 1 when a miss is found; the residual is the acceptance number.
"""
import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
import select_tests as st  # noqa: E402

MAX_READERS = 20
# The declared residual — code-critic R338's acceptance number. Each entry says why no
# static rule can see the read. A NEW miss fails the audit; one of these does not.
KNOWN_RESIDUAL = {
    "machine_learning/models/v3/algo_stream_estimates.json":
        "read by the render path through a path built at run time — no module names it",
    ".claude/scripts/audit_collectors_ast.py":
        "read by a script the test runs, not by the test — a subprocess read the trace "
        "attributes to the test but no import or name can carry",
    # AppTest renders load the app by FILE PATH, not by import: an image the page shows is
    # read by those tests, and no import edge leads from it to them (audit of 2026-09-29).
    "assets/credential_guide/spotify/spotify_share_artist_link.png":
        "shown by a page an AppTest renders by file path — outside the import graph",
    "src/dashboard/assets/examples/dashboard-global-thumb.png":
        "embedded in the verification e-mail by path — outside the import graph",
    "src/dashboard/assets/logo_horizontal_adaptive.svg":
        "shown by a page an AppTest renders by file path — outside the import graph",
}


def trace() -> dict[str, set[str]]:
    out = tempfile.mkdtemp(prefix="select-trace-")
    env = {**os.environ, "SELECT_TRACE_OUT": out, "SELECT_TRACE_ROOT": str(ROOT),
           "PYTHONPATH": f"{ROOT / 'tools' / 'dev'}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "-p", "select_trace_plugin",
                    "-n", os.environ.get("PYTEST_WORKERS", "2")],
                   cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reads: dict[str, set[str]] = defaultdict(set)
    for f in Path(out).glob("*.json"):
        for mod, files in json.loads(f.read_text()).items():
            reads[mod] |= set(files)
    return reads


def probes(reads: dict[str, set[str]], tracked: set[str]) -> dict[str, set[str]]:
    """{probe file: the test modules that read it}, one probe per directory. Pure."""
    readers: dict[str, set[str]] = defaultdict(set)
    for mod, files in reads.items():
        for f in files:
            if f in tracked and not st.is_test(f) and f != mod:
                readers[f].add(mod)
    by_dir: dict[str, str] = {}
    for f in sorted(readers):
        if 1 <= len(readers[f]) <= MAX_READERS:
            by_dir.setdefault(str(Path(f).parent), f)
    return {f: readers[f] for f in by_dir.values()}


def main() -> int:
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True).stdout.split())
    reads = trace()
    if not reads:
        print("❌ la trace est vide — le plugin n'a rien enregistré, l'audit ne prouve rien")
        return 2
    misses = {}
    for f, who in probes(reads, tracked).items():
        r = st.select(ROOT, _changed=[f])
        if r["all"]:
            continue
        picked = set(r.get("paths") or [])
        lost = sorted(m for m in who if m not in picked)
        if lost:
            misses[f] = lost
    known = {f: v for f, v in misses.items() if f in KNOWN_RESIDUAL}
    new = {f: v for f, v in misses.items() if f not in KNOWN_RESIDUAL}
    for f, lost in sorted(known.items()):
        print(f"résidu déclaré  {f} → {', '.join(lost)} ({KNOWN_RESIDUAL[f]})")
    for f, lost in sorted(new.items()):
        print(f"RATÉ  {f} → {', '.join(lost)}")
    print(f"{len(new)} raté(s) nouveau(x), {len(known)} résidu(s) déclaré(s)")
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
