#!/usr/bin/env python3
"""Signature for `message-flattened-for-the-narrowest-renderer`.

Exits non-zero when a probe diagnosis is flattened to its first line, or reaches an
HTML cell without being rendered. Reads the AST, never the text: the modules it
inspects *describe* the defect in their own comments, and a string search fails on
the explanation instead of the code — the lesson of the four hollow guards of
2026-08-22.

---
rex:
  - date: 2026-08-26
    issue: "`platform_probes` returned `splitlines()[0]` of a two-part diagnosis, so the nightly alert named the problem and dropped the gesture that fixes it — both red rows of the 2026-08-26 production mail."
    fix: "Added `src/utils/diagnosis_text.py` (one renderer per surface), removed the flattening, and wired the four consumer sites. This signature reads the AST of the consumers."
    severity: warn
---
"""
from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

CONSUMERS = [
    "src/utils/platform_probes.py",
    "src/dashboard/utils/status_matrix.py",
    "tools/artist_preflight.py",
    "airflow/dags/alert_monitor.py",
]
CARRIERS = {"next_action", "reason"}


def _names_in(node: ast.AST) -> set:
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            found.add(sub.id)
        elif isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
            if isinstance(sub.slice.value, str):
                found.add(sub.slice.value)
    return found


def _is_markup(joined: ast.JoinedStr) -> bool:
    literal = "".join(p.value for p in joined.values
                      if isinstance(p, ast.Constant) and isinstance(p.value, str))
    return "<" in literal and ">" in literal


def main() -> int:
    hits: list[str] = []
    for rel in CONSUMERS:
        path = REPO / rel
        if not path.exists():
            hits.append(f"{rel}: MISSING — the guard's scope moved, not the defect")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute)
                    and node.value.func.attr == "splitlines"
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value == 0):
                hits.append(f"{rel}:{node.lineno}: diagnosis flattened to its first "
                            f"line — the half that says what to DO is dropped")

        for joined in ast.walk(tree):
            if not isinstance(joined, ast.JoinedStr) or not _is_markup(joined):
                continue
            for node in joined.values:
                if not isinstance(node, ast.FormattedValue):
                    continue
                if not (_names_in(node.value) & CARRIERS):
                    continue
                call = node.value
                if not (isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Name)
                        and call.func.id == "as_html"):
                    hits.append(f"{rel}:{node.lineno}: diagnosis reaches an HTML cell "
                                f"without as_html() — breaks and emphasis dropped, "
                                f"and a platform's own `<` goes in raw")

    for h in hits:
        print(h)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
