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
    """[{site, kind ('figure'|'pdf'), fn, visible, layer, sources}] — one per code site."""
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    import gold_coverage as gc
    gold, known = gc.scan_sql()
    files = gc.load_python()
    calls = gc.build_call_index(files)
    slicer = gc.Slicer(files, calls, gold, known, gc.sql_wrappers(files))
    out = []
    for s in gc.collect_surfaces(files, slicer) + gc.collect_pdf(files, slicer):
        if s.kind not in ("figure", "pdf"):
            continue
        out.append({"site": f"{s.rel}:{s.line}", "kind": s.kind, "fn": s.fn,
                    "visible": s.visible, "layer": gc.layer_of(s.sl),
                    "sources": sorted(name for _, name in s.sl.sources)})
    return out
