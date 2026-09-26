"""The static list of every figure site, with its data source and layer — from gold-coverage.

Type: Utility
Uses: tools/dev/gold_coverage.py (load_python, build_call_index, Slicer, collect_surfaces,
      collect_pdf, layer_of, scan_sql, sql_wrappers)
Triggers: tools/dev/charts_dossier/main.py, tests/test_the_charts_dossier_covers_every_figure.py
Persists in: nothing

R203 (2026-09-26). The capture sees what a DEFAULT render draws; this sees every code site that
CAN draw. The dossier needs both: a site with no image is listed with its reason, never
dropped — the same rule as the capture's « not rendered ».
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sites() -> list[dict]:
    """[{site, key, kind ('figure'|'pdf'), fn, visible, layer, sources}] — one per code site.

    `key` is STABLE: `file::function#n`, the n-th figure of that function in source order.
    `site` (`file:line`) moves at every edit above it; keyed by it, the owner's comments
    detached from their chart after the first merge (2026-09-26, R205/R216)."""
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    import gold_coverage as gc
    gold, known = gc.scan_sql()
    files = gc.load_python()
    calls = gc.build_call_index(files)
    slicer = gc.Slicer(files, calls, gold, known, gc.sql_wrappers(files))
    import collections
    out, nth = [], collections.Counter()
    surfaces = [s for s in gc.collect_surfaces(files, slicer) + gc.collect_pdf(files, slicer)
                if s.kind in ("figure", "pdf")]
    for s in sorted(surfaces, key=lambda s: (s.rel, s.line)):
        nth[(s.rel, s.fn)] += 1
        out.append({"site": f"{s.rel}:{s.line}", "key": f"{s.rel}::{s.fn}#{nth[(s.rel, s.fn)]}",
                    "kind": s.kind, "fn": s.fn, "visible": s.visible,
                    "layer": gc.layer_of(s.sl),
                    "sources": sorted(name for _, name in s.sl.sources)})
    return out
