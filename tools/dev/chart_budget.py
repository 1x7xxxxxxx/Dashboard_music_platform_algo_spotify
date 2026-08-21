#!/usr/bin/env python3
"""Report how many charts each dashboard view renders. REPORT-ONLY, on purpose.

Type: Utility
Uses: nothing (stdlib)
Triggers: `make chart-budget`
Persists in: nothing

Why report-only and not a failing check: nobody here has a SOURCE for "N charts per
view is too many". The knowledge corpus was queried on 2026-08-21 for dashboard
ergonomics and returned nothing above noise (best score 0.016) — the `ux-frontend`
domain is empty, which is roadmap item R17.

Enforcing a threshold now would mean inventing one and dressing it as a rule. What
CAN be done without a source is remove the guesswork from the OTHER half of the
question: how many are there today, and which views are unlike their neighbours.
That much is measurable, and it is what this prints.

Measured 2026-08-21: 22 views carry charts, 83 charts total, median 3, and four
views sit above twice the median — `trigger_algo` at 15 is five times it.

Read the outliers as "worth a look", never as "too many".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VIEWS = ROOT / "src/dashboard/views"

CHART = re.compile(
    r"st\.(plotly_chart|altair_chart|bar_chart|line_chart|area_chart|pyplot|map)\b")


def counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for entry in sorted(VIEWS.iterdir()):
        if entry.is_file() and entry.suffix == ".py":
            files, name = [entry], entry.stem
        elif entry.is_dir():
            files, name = sorted(entry.rglob("*.py")), entry.name
        else:
            continue
        n = sum(len(CHART.findall(f.read_text(encoding="utf-8", errors="ignore")))
                for f in files)
        if n:
            out[name] = n
    return out


def main() -> int:
    data = counts()
    if not data:
        print("no view renders a chart — check the path", file=sys.stderr)
        return 1
    values = sorted(data.values())
    median = values[len(values) // 2]
    print(f"{len(data)} view(s) carry charts · {sum(values)} total · median {median}")
    print()
    for name, n in sorted(data.items(), key=lambda kv: -kv[1]):
        mark = "  ← above twice the median" if n > 2 * median else ""
        print(f"  {n:>3}  {name}{mark}")
    print()
    print("Report only. There is no sourced threshold — the ux-frontend corpus is")
    print("empty (roadmap R17). Outliers are worth a look, not automatically wrong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
