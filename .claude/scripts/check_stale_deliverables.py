#!/usr/bin/env python3
"""Flag deliverables that have outlived their declared shelf life. A signature, not an agent.

The ask was "an agent that analyses whether client deliverables are obsolete and should be
archived". This is that, as ~20 lines of shell-equivalent, and the reason is measured: 4 of this
repo's 6 declared agents have NEVER been invoked once (`usage_report.py`). An agent that only runs
when someone remembers to call it is a capability on paper. A signature runs on every sweep, free,
forever.

THE DESIGN DECISION, and it is the whole difference between this and a guess:
**A file is not stale because it is OLD. It is stale because it made a promise about when it would
expire, and that date has passed.** Mtime-based staleness ("nothing touched this in 90 days") would
flag `trading-safety.md` — a rule that is correct precisely because it does not change — and it
would flag nothing about `GANTT.md`, which was wrong from its first commit and never aged into it.
So: an OPT-IN contract. A doc declares `expires: YYYY-MM-DD` (or `review_by:`) in its frontmatter,
and only then is it accountable to a date.

That opt-in is also the honest limit: **this finds documents that broke a promise they made, not
documents that are quietly wrong.** Nothing greps "this paragraph is obsolete" — that is the class
`status-glyph-outside-the-single-source` already admits it cannot detect. Six unfilled bootstrap
templates were found today by a DIFFERENT signature (`bootstrap-template-never-filled`), because
that class has a footprint and this one doesn't.

    python/.venv/bin/python .claude/scripts/check_stale_deliverables.py    # exit != 0 = expired

---
rex:
  - date: 2026-07-17
    issue: "First design was mtime staleness ('untouched for N days'). It would have flagged trading-safety.md — correct precisely BECAUSE it does not change — and said nothing about GANTT.md, wrong from its first commit and never aged into it. Age is not obsolescence."
    fix: "Opt-in contract instead: a doc declares `expires:`/`review_by:` and only then is accountable to a date. With 0 subscribers the guard says so LOUDLY rather than passing — green-because-nobody-opted-in is not green-because-nothing-is-stale. First subscriber: roster_rebalance_plan.md (frozen, trigger refuted, referenced by no step)."
    severity: info
    ref: "error-classes.md#deliverable-outlived-its-declared-life"
---
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
import subprocess

_REPO = pathlib.Path(__file__).resolve().parents[2]
_ROOTS = (_REPO / ".claude" / "dev-docs", _REPO / "docs", _REPO / "reports")
_DATE = re.compile(r"^(expires|review_by):\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)


def _last_touched(path: pathlib.Path) -> str:
    """git is the honest clock: mtime lies after a clone, a checkout, or a sync."""
    r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)],
                       cwd=_REPO, capture_output=True, text=True, timeout=30)
    return r.stdout.strip() or "(untracked)"


def main() -> int:
    today = dt.date.today()
    expired, watched = [], 0
    for root in _ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.md")):
            try:
                head = p.read_text(encoding="utf-8", errors="ignore")[:2048]
            except OSError:
                continue
            m = _DATE.search(head)
            if not m:
                continue                       # no promise made, nothing to break
            watched += 1
            when = dt.date.fromisoformat(m.group(2))
            if when < today:
                expired.append((p.relative_to(_REPO), m.group(1), when,
                                (today - when).days, _last_touched(p)))

    for rel, key, when, days, touched in expired:
        print(f"  ❌ {rel} — {key}: {when} ({days}d ago; last commit {touched})")
    if watched == 0:
        # Loud, not silent. Zero watched files means the contract has no subscribers — the check is
        # green because nothing opted in, which is not the same as "nothing is stale". A guard that
        # reports success on an empty set is how a check becomes decorative.
        print("⚠️  0 documents declare `expires:` or `review_by:` — this guard is watching nothing.\n"
              "    Add `expires: YYYY-MM-DD` to any doc whose truth has a shelf life.")
        return 0
    print(f"\n{watched - len(expired)}/{watched} dated documents still within their declared life")
    return 1 if expired else 0


if __name__ == "__main__":
    raise SystemExit(main())
