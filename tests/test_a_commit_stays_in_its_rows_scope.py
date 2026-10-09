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


def test_a_non_product_file_outside_the_scope_is_refused_too():
    """R450 — 2026-10-07: a commit « R449 » (scope tools/dev/, tests/) carried R448's
    ci.yml; only product paths were judged, so nothing said so."""
    row = ("| R449 | x <!-- critic: non — outil --> <!-- scope: tools/dev/, tests/, "
           ".test_durations --> | P4 | m |")
    bad = gate.verdict([".github/workflows/ci.yml", "tools/dev/night_run.py"],
                       "R449 : x", _checklist(row))
    assert bad and ".github/workflows/ci.yml" in bad and "night_run" not in bad
    assert gate.verdict(["tools/dev/night_run.py", "tests/test_y.py", ".test_durations"],
                        "R449 : x", _checklist(row)) is None
    closing = [".claude/dev-docs/roadmap/checklist.md", ".claude/dev-docs/roadmap/archive.md"]
    assert gate.verdict(closing, "Roadmap : R449 close", _checklist(row)) is None
    assert gate.verdict(["Makefile"], "R450 : not open here", _checklist(row)) is None


def test_a_row_quoting_the_marker_syntax_keeps_its_real_scope():
    """R450's own row quoted `<!-- scope: … -->` in its text; read first, it became the scope."""
    row = ("| R450 | judged by (`<!-- scope: … -->`) <!-- critic: non — x --> "
           "<!-- scope: tools/dev/, tests/ --> | P3 | m |")
    assert gate.scope_of(row) == ["tools/dev/", "tests/"]


def _paths_built_under_root(source: str) -> set[str]:
    """Every `ROOT / "a" / "b" / …` chain of string literals, joined — the files a tool
    reads or writes in the repo, read from the AST, never from a variable name. Pure."""
    import ast
    import os

    def parts(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = parts(node.left)
            if left is not None and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
                return left + [node.right.value]
            return None
        return [] if isinstance(node, ast.Name) and node.id == "ROOT" else None

    out = set()
    for node in ast.walk(ast.parse(source)):
        p = parts(node)
        if p and os.path.splitext(p[-1])[1]:  # a file, not a dot-directory
            out.add("/".join(p))
    return out


def test_every_file_roadmap_close_writes_is_roadmap_bookkeeping():
    """R490 — 2026-10-09: `make roadmap-close R474` rewrote notes-triage.yaml (R268) and
    the commit-msg gate refused the closing commit, the file being outside R474's scope.
    A file the closing tool writes is bookkeeping, like the archive : never judged."""
    src = (ROOT / "tools/dev/roadmap.py").read_text(encoding="utf-8")
    written = _paths_built_under_root(src)
    assert ".claude/dev-docs/architecture/notes-triage.yaml" in written, "le détecteur ne voit plus le fichier"
    row = "| R474 | x <!-- critic: non --> <!-- scope: src/dashboard/, tests/ --> | P2 | m |"
    assert gate.out_of_scope(sorted(written), [row]) == [], "roadmap-close écrit hors comptabilité"
    assert gate.out_of_scope(["src/api/main.py"], [row]) == ["src/api/main.py"], "le garde ne juge plus rien"


def test_the_root_path_detector_reads_the_chain():
    """Non-vacuité : la chaîne `ROOT / "x" / "y.md"` est vue, un nom ou un dossier ne l'est pas."""
    assert _paths_built_under_root('p = ROOT / ".claude" / "a.yaml"') == {".claude/a.yaml"}
    assert not _paths_built_under_root('p = OTHER / ".claude" / "a.yaml"')
    assert not _paths_built_under_root('p = ROOT / ".claude" / "dir"')
