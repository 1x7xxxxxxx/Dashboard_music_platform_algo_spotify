#!/usr/bin/env python3
r"""Lint dashboard view files for known anti-patterns. Non-blocking PostToolUse.

Scans src/dashboard/views/*.py after Write/Edit for two patterns that have
caused runtime bugs:

1. `.style.format(...)` without `na_rep` — pandas styler crashes on NULL
   values coming from LEFT JOIN / NULLIF / empty aggregates.
   Reference: src/dashboard/views/trigger_algo.py:411

2. `make_subplots(...subplot_titles=...vertical_spacing=0.0[1-4])` — Plotly
   silently renders zero-height plot rows when titles consume the layout
   budget. Fix: vertical_spacing ≥ 0.05 OR use px.bar(facet_row=...).
   Reference: src/dashboard/views/meta_ads_overview.py "Comparaison multi-métriques"

Always exits 0 — informational only.

---
rex:
  - date: 2026-05-14
    issue: "No automated lint scanned views for .style.format-without-na_rep or make_subplots\
  \ tight-spacing; silent runtime bugs"
    fix: "Created PostToolUse hook scanning src/dashboard/views/*.py post-Write/Edit; warns\
  \ on .style.format(no na_rep) + make_subplots(subplot_titles + vertical_spacing<0.05)"
    severity: "info"
    ref: "DEVLOG#2026-05-14"
---
"""
import json
import pathlib
import ast
import re
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    tool = data.get("tool_name") or data.get("name")
    if tool not in ("Edit", "Write"):
        return

    fp_str = data.get("tool_input", {}).get("file_path", "")
    if not fp_str:
        return
    fp = pathlib.Path(fp_str)
    if fp.suffix != ".py":
        return
    if "dashboard/views" not in str(fp).replace("\\", "/"):
        return

    try:
        content = fp.read_text(encoding="utf-8")
    except OSError:
        return

    warnings = []

    # `.style.format(...)` sans `na_rep` — lu sur l'ARBRE.
    #
    # La version textuelle cherchait « na_rep » dans les 500 caractères suivants :
    # un commentaire ou une docstring y suffisait à supprimer l'avertissement, sur
    # un appel réellement non protégé. C'est le mécanisme de détection cité par la
    # classe `df-na-rep` du catalogue, et il portait la même faiblesse que six
    # `signature.cmd` corrigées le 2026-09-04.
    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None                 # un fichier en cours d'écriture : rien à dire
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if getattr(func, "attr", None) != "format":
                continue
            if getattr(getattr(func, "value", None), "attr", None) != "style":
                continue
            if any(k.arg == "na_rep" for k in node.keywords):
                continue
            warnings.append(
                f"  L{node.lineno}: .style.format(...) without na_rep "
                "→ see dashboard-view.md pitfall #1"
            )

    for m in re.finditer(r"make_subplots\s*\((.*?)\)", content, re.DOTALL):
        body = m.group(1)
        if "subplot_titles" in body and re.search(
            r"vertical_spacing\s*=\s*0\.0[1-4]", body
        ):
            line = content[: m.start()].count("\n") + 1
            warnings.append(
                f"  L{line}: make_subplots + subplot_titles + tight vertical_spacing → see dashboard-view.md pitfall #2"
            )

    if warnings:
        print(f"⚠️  dashboard-view lint ({fp}):", file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)


if __name__ == "__main__":
    main()
