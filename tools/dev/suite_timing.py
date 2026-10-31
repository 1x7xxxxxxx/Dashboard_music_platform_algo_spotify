#!/usr/bin/env python3
"""Write the full suite's measured time — the ONE place the number lives (R268).

Type: Utility
Uses: .pytest-last.log (written by `make test`)
Writes: .claude/dev-docs/test-suite-timing.json
Triggers: make test (after the run) ; tests/test_a_delivery_closes_on_a_green_ci.py

Measured 2026-09-27 : the Makefile help and CLAUDE.md both announced « 180 s », a figure of
2026-09-25 ; the suite ran 372 s for 10 931 tests the same evening. A timing written by hand
in two places is two numbers that age separately — the run writes its own.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".claude" / "dev-docs" / "test-suite-timing.json"
# A pytest summary line ends in « in <seconds>s » and lists its counters in pytest's own
# order (failed, passed, skipped, …, errors) — R683: a regex that fixed `passed` before
# `failed` read `failed: 0` on every red suite. Each counter is read on its own.
_SUMMARY = re.compile(r"\b\d+ (?:failed|passed|errors?)\b.*? in ([\d.]+)s")
_COUNT = re.compile(r"(\d+) (failed|passed|errors?)\b")


def parse(log: str) -> dict | None:
    """The last pytest summary line of a log → {passed, failed, seconds}. Pure.

    `failed` counts errors too: both make the suite red.
    """
    found = None
    for line in log.splitlines():
        m = _SUMMARY.search(line)
        if not m:
            continue
        counts = {"passed": 0, "failed": 0}
        for n, kind in _COUNT.findall(line):
            counts["passed" if kind == "passed" else "failed"] += int(n)
        found = {**counts, "seconds": round(float(m.group(1)))}
    return found


def main(workers: str = "?") -> int:
    log = ROOT / ".pytest-last.log"
    got = parse(log.read_text(encoding="utf-8", errors="replace")) if log.is_file() else None
    if got is None:
        print("⚠️  aucun résumé pytest dans .pytest-last.log — rien écrit")
        return 0
    got.update(date=dt.date.today().isoformat(), workers=workers)
    OUT.write_text(json.dumps(got, indent=1) + "\n", encoding="utf-8")
    print(f"▶ temps de suite : {got['seconds']} s, {got['passed']} verts, {workers} worker(s) → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "?"))
