#!/usr/bin/env python3
"""Remove from graphify-out/graph.json the nodes of files that no longer exist on disk.

Type: Utility
Uses: graphify-out/graph.json (networkx node-link JSON)
Triggers: `make graph-update`, after `graphify update .`
Persists in: graphify-out/graph.json (gitignored, local)

R269 (owner notes L166, L169). `graphify update` ADDS and never removes: a deleted or
renamed module keeps its nodes, and GRAPH_REPORT.md then sends the reader to a file that is
gone. Measured: 24 ghost files / 177 nodes on 2026-09-11 — a residue that grew at every
regeneration — and still 2 files / 4 nodes right after a fresh rebuild on 2026-09-27.
Guard: tests/test_the_code_graph_carries_no_ghost_file.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / "graphify-out" / "graph.json"


def prune(graph: dict, exists: Callable[[str], bool]) -> tuple[dict, list[str]]:
    """(graph without the ghost files' nodes and their links, sorted ghost files). Pure."""
    ghosts = sorted({n["source_file"] for n in graph.get("nodes", [])
                     if n.get("source_file") and not exists(n["source_file"])})
    if not ghosts:
        return graph, []
    gone = set(ghosts)
    dead = {n["id"] for n in graph["nodes"] if n.get("source_file") in gone}
    out = dict(graph)
    out["nodes"] = [n for n in graph["nodes"] if n["id"] not in dead]
    out["links"] = [e for e in graph.get("links", [])
                    if e.get("source") not in dead and e.get("target") not in dead]
    return out, ghosts


def main() -> int:
    if not GRAPH.is_file():
        print(f"❌ {GRAPH.relative_to(ROOT)} absent — lancer : graphify update .", file=sys.stderr)
        return 1
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    pruned, ghosts = prune(graph, lambda p: (ROOT / p).exists())
    if ghosts:
        GRAPH.write_text(json.dumps(pruned), encoding="utf-8")
    removed = len(graph["nodes"]) - len(pruned["nodes"])
    print(f"graphify : {len(ghosts)} fichier(s) fantôme(s), {removed} nœud(s) retiré(s)"
          + (f" — {', '.join(ghosts[:5])}" if ghosts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
