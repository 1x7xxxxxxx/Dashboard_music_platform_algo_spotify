"""R268 (REQ-ROAD-04) — a code commit stays inside the scope its roadmap row declares.

Type: Test
Uses: tools/dev/require_roadmap_id.py (verdict, out_of_scope, open_rows),
      .claude/dev-docs/roadmap/checklist.md

Before R268 the gate proved that SOME open row was cited, never that the diff was that
row's task: with seventeen rows open, any commit could cite any of them. A row now declares
`<!-- scope: src/a, src/b -->`; a commit citing it may only touch product files under those
paths. Rows inscribed from R279 on must declare a scope — older rows are not judged.

Mutation record (2026-09-27) : `out_of_scope` returning [] → red ; the R279 floor removed
from the declaration check → red on the synthetic undeclared row.
"""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("roadmap_gate", ROOT / "tools/dev/require_roadmap_id.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

FIRST_SCOPED = 279


def _checklist(row: str) -> str:
    return f"{gate.INDEX_TITLE}\n\n| id | Tâche | P | Mesuré par |\n|---|---|---|---|\n{row}\n"


def test_a_file_outside_the_declared_scope_is_refused():
    row = ("| R300 | x <!-- critic: non — outil --> <!-- scope: src/dashboard/utils/filters.py, "
           "src/dashboard/views/meta_ads_overview.py --> | P3 | m |")
    ok = gate.verdict(["src/dashboard/utils/filters.py"], "R300 : x", _checklist(row))
    assert ok is None
    bad = gate.verdict(["src/dashboard/views/home.py"], "R300 : x", _checklist(row))
    assert bad and "hors du périmètre" in bad
    assert gate.verdict(["tests/test_x.py", "src/dashboard/utils/filters.py"],
                        "R300 : x", _checklist(row)) is None, "tests are not product code"


def test_a_row_without_scope_is_not_judged():
    row = "| R250 | x <!-- critic: non — outil --> | P3 | m |"
    assert gate.verdict(["src/anything.py"], "R250 : x", _checklist(row)) is None


def undeclared(checklist: str, first: int = FIRST_SCOPED) -> list[str]:
    """Open rows from `first` on that declare no scope. Pure."""
    return sorted(rid for rid, row in gate.open_rows(checklist).items()
                  if int(re.sub(r"\D", "", rid)) >= first and gate.scope_of(row) is None)


def test_every_new_row_declares_its_scope_not_vacuous():
    with open(ROOT / ".claude/dev-docs/roadmap/checklist.md", encoding="utf-8") as fh:
        live = undeclared(fh.read())
    assert not live, f"lignes ≥ R{FIRST_SCOPED} sans `<!-- scope: … -->` : {live}"
    assert undeclared(_checklist("| R300 | x <!-- critic: non --> | P3 | m |")) == ["R300"]
