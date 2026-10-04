"""REQ-OBS-02 — what Grafana traces is not said again in an admin view, and the map says where (R364).

The proof used to be `test -f grafana-correspondence.md`: no code change could ever turn it
red (mutated 2026-10-04). Two properties replace it: every panel the correspondence points
to still exists under that title, and the process gauges Grafana took over (RAM, CPU —
panels 8 and 9) are not measured again by the dashboard.
"""
from __future__ import annotations

import ast
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/dev-docs/grafana-correspondence.md"
BOARD = ROOT / "deploy/grafana/dashboards/streamlytics-ops.json"


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def cited_panels(doc: str) -> set[str]:
    return {_fold(t) for t in re.findall(r"Panneau \d+ « ([^»]+) »", doc)}


def test_every_panel_the_correspondence_cites_exists() -> None:
    cited = cited_panels(DOC.read_text(encoding="utf-8"))
    assert len(cited) >= 4, "the correspondence must keep naming the panels it relies on"
    titles = {_fold(p.get("title", "")) for p in json.loads(BOARD.read_text(encoding="utf-8"))["panels"]}
    missing = cited - titles
    assert not missing, f"the correspondence points to panels that no longer exist: {missing}"


def imports_psutil(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        if any(n.split(".")[0] == "psutil" for n in names):
            return True
    return False


def test_the_dashboard_does_not_measure_the_process_again() -> None:
    hits = [str(p.relative_to(ROOT)) for p in (ROOT / "src/dashboard").rglob("*.py")
            if imports_psutil(p.read_text(encoding="utf-8"))]
    assert not hits, f"process RAM/CPU live in Grafana panels 8-9, not in a view: {hits}"


def test_the_detector_sees_an_import_not_a_comment() -> None:
    assert imports_psutil("def f():\n    import psutil\n")
    assert imports_psutil("from psutil import Process\n")
    assert not imports_psutil("# import psutil\nx = 'import psutil'\n")


def test_the_detector_sees_a_renamed_panel() -> None:
    assert cited_panels("Panneau 8 « Processus — RAM résidente » x") == {_fold("processus — ram residente")}
