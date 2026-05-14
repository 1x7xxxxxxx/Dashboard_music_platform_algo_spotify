#!/usr/bin/env python3
"""Regenerate graphify-out/graph.html from the current graph.json.

The graphify CLI exposes `update` (refresh graph.json + GRAPH_REPORT.md) but
NOT a command to re-render the interactive HTML. This helper calls
`graphify.export.to_html` directly and lifts the hard-coded
`MAX_NODES_FOR_VIZ=5000` cap so streamlytics' 1.5k-node graph (and any future
growth) fits without re-bumping the constant.

Usage:  python3 tools/dev/graphify_render_html.py
        (run from repo root — paths are relative to graphify-out/)
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import graphify.export as ex

GRAPH_JSON = Path("graphify-out/graph.json")
GRAPH_HTML = Path("graphify-out/graph.html")


def main() -> None:
    if not GRAPH_JSON.exists():
        raise SystemExit(f"missing {GRAPH_JSON} — run `graphify update .` first")

    ex.MAX_NODES_FOR_VIZ = 100_000

    data = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    data_nx = {k: v for k, v in data.items() if k != "hyperedges"}
    G = nx.node_link_graph(data_nx, edges="links")

    communities: dict[int, list[str]] = {}
    for n, attrs in G.nodes(data=True):
        communities.setdefault(attrs.get("community", 0), []).append(n)

    labels: dict[int, str] = {}
    for c in data.get("graph", {}).get("communities", []) or []:
        cid = c.get("id")
        if cid is not None:
            labels[cid] = c.get("label", f"Community {cid}")

    ex.to_html(G, communities, str(GRAPH_HTML), community_labels=labels)
    print(
        f"{GRAPH_HTML} regenerated — "
        f"{G.number_of_nodes()} nodes / {G.number_of_edges()} edges / "
        f"{len(communities)} communities"
    )


if __name__ == "__main__":
    main()
