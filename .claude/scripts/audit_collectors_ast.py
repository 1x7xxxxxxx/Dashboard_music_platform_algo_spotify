#!/usr/bin/env python3
"""
collector-silent-success — precise AST detector.

The grep signature is noisy (matches legit success-path `return data`) AND blind
to the partial-return variant (`return comments`). Per the audit-collectors.md
REX, the exact detector is: **any `return` of a value/None/empty inside an
`except` block that does not itself `raise`** → the collector swallows the error,
the DAG exits SUCCESS on 0/partial rows, the dashboard goes silently stale.

Exit 1 on any hit (error-class catalogue contract: non-zero = anti-pattern present).
Excluded (documented false positive): `return True/False` — bool-STATUS helpers
whose contract IS a bool and on which no upsert depends (e.g. `_refresh_access_token`).

Usage: audit_collectors_ast.py [path ...]   # default: src/collectors/*.py

Type: Utility (Claude Code config)
Uses: ast
Persists in: — (stdout report + exit code)

---
rex:
  - date: 2026-06-13
    issue: "collector-silent-success grep was noisy and missed return-partial-in-except; no precise AST detector existed"
    fix: "audit_collectors_ast.py flags non-raising returns inside except blocks (bool-status returns excluded); wired as the class signature"
    ref: "DEVLOG#2026-06-13-suite22"
    severity: warn
---
"""
import ast
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _handler_raises(handler: ast.ExceptHandler) -> bool:
    """True if this except handler re-raises (anywhere in its body)."""
    return any(isinstance(n, ast.Raise) for n in ast.walk(handler))


def _silent_returns(handler: ast.ExceptHandler) -> list[int]:
    """Line numbers of value/None/empty returns in an except that does NOT raise."""
    if _handler_raises(handler):
        return []
    out = []
    for n in ast.walk(handler):
        if isinstance(n, ast.Return):
            v = n.value
            if isinstance(v, ast.Constant) and isinstance(v.value, bool):
                continue  # bool-status helper — documented FP
            out.append(n.lineno)
    return out


def scan(path: Path) -> list[int]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return []
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            hits.extend(_silent_returns(node))
    return sorted(hits)


def main() -> None:
    args = sys.argv[1:]
    files = [Path(a) for a in args] if args else sorted((_REPO / "src" / "collectors").glob("*.py"))
    total = 0
    for f in files:
        for ln in scan(f):
            rel = f.relative_to(_REPO) if f.is_absolute() and str(f).startswith(str(_REPO)) else f
            print(f"  {rel}:{ln}  non-raising return inside except (silent-success)")
            total += 1
    if total:
        print(f"⚠ {total} silent-success candidate(s) — collector except block returns without raising")
        sys.exit(1)
    print("✅ no silent-success in collectors")
    sys.exit(0)


if __name__ == "__main__":
    main()
