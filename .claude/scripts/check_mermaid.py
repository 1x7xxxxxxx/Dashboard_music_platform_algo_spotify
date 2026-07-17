#!/usr/bin/env python3
"""Validate every mermaid block in the docs. A linter, not an agent — and that is the decision.

The ask was "an agent that owns mermaid diagram formatting so we don't scatter". Measured: there are
**4 files** with mermaid blocks in this repo, and `mmdc` (the official mermaid CLI) is already
installed. An agent for four diagrams a shell command can validate is the most expensive possible way
to run a linter: it costs tokens, it returns prose someone must read and believe, and it only runs
when someone remembers to call it — and this repo's own numbers say 4 of its 6 agents have never been
called once.

A signature costs ~0 and runs on every sweep, forever. That is the whole "detector over agent" rule,
applied to the smallest possible case so the shape is visible.

Scope, honestly: `mmdc` checks that a diagram PARSES and RENDERS. It cannot check that the diagram is
TRUE — that the boxes match the code. That is `code-architecture-reviewer`'s remit (0 invocations,
see CLAUDE.md) and it is irreducibly semantic. This guard stops a broken diagram from shipping; it
does not stop a lying one. Do not let a green run here be read as "the architecture doc is correct" —
the Mermaid in this repo "asserted things that were false" for weeks, and it parsed fine the whole
time.

    python/.venv/bin/python .claude/scripts/check_mermaid.py        # exit != 0 on a malformed block

---
rex:
  - date: 2026-07-17
    issue: "Asked for an agent to own mermaid formatting. Measured: 4 mermaid files in the whole repo, mmdc already installed, and 4 of 6 declared agents have never been invoked once — an agent that runs only when remembered is a capability on paper."
    fix: "A linter instead (mmdc -i <f> -o /dev/null per block), swept by audit_runner. It found GANTT.md broken on its FIRST run — 'Invalid date: YYYY-MM-DD', invalid since the bootstrap commit. Limit written into the class: mmdc proves a diagram PARSES, never that it is TRUE."
    severity: info
    ref: "error-classes.md#mermaid-block-does-not-render"
---
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
_ROOTS = (_REPO / ".claude" / "dev-docs",)
_BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)


def _mmdc() -> str | None:
    found = shutil.which("mmdc")
    if found:
        return found
    hits = sorted(pathlib.Path.home().glob(".nvm/versions/node/*/bin/mmdc"))
    return str(hits[-1]) if hits else None


def main() -> int:
    exe = _mmdc()
    if exe is None:
        # Loud, not silent. A validator that shrugs when its tool is missing reports "clean" on an
        # unchecked repo — the exact silent-pass this project keeps finding.
        print("🔴 mmdc not found — cannot validate. Install @mermaid-js/mermaid-cli or fix the path.")
        return 2

    blocks = [(p, i, m.group(1)) for root in _ROOTS for p in sorted(root.rglob("*.md"))
              for i, m in enumerate(_BLOCK.finditer(p.read_text(encoding="utf-8", errors="ignore")), 1)]
    if not blocks:
        print("no mermaid blocks found — nothing to validate")
        return 0

    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        for path, idx, src in blocks:
            f = pathlib.Path(tmp) / f"b{idx}.mmd"
            f.write_text(src, encoding="utf-8")
            r = subprocess.run([exe, "-i", str(f), "-o", str(f.with_suffix(".svg"))],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                err = (r.stderr or r.stdout or "").strip().splitlines()
                bad.append(f"{path.relative_to(_REPO)} block #{idx}: {err[-1] if err else 'failed'}")

    for b in bad:
        print(f"  ❌ {b}")
    print(f"\n{len(blocks) - len(bad)}/{len(blocks)} mermaid blocks valid")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
