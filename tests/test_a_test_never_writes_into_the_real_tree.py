"""A test writes its probes under tmp_path — never into the repository it shares with other tests.

Type: Sub
Uses: tests/*.py (AST only)
Depends on: nothing

2026-09-25, random-order nightly: `test_the_archives_are_really_dead` failed with
FileNotFoundError on `src/dashboard/_probe_platform_colour.py`. Another test had written its
probe into the REAL `src/dashboard/`, and under xdist a third test's `rglob` listed it and then
lost it. The sibling sweep found five more probes of the same shape (views/, utils/, tests/,
and a `NamedTemporaryFile(dir=ROOT)`), all fixed the same day. This guard refuses the shape.

A write into the tree stays legitimate when it is SERIALISED and declared: the files below
carry an `xdist_group` and touch a path no scanner reads.
"""
import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_WRITES = {"write_text", "write_bytes", "touch", "unlink", "rename", "replace", "mkdir"}
_TEMP_FACTORIES = {"NamedTemporaryFile", "TemporaryDirectory", "mkdtemp", "mkstemp"}
# Declared, serialised writers — each with the reason it is safe.
_DECLARED = {
    "test_a_bash_guard_reads_the_command_not_the_prose.py": "xdist_group('writes-readme'), README only",
    "test_a_restore_does_not_erase_unsaved_work.py": "xdist_group('writes-readme'), README only",
    "test_an_imported_file_survives_its_import.py": "xdist_group, data/uploads/999999 — no scanner reads it",
}


def _rooted_names(tree: ast.Module) -> set[str]:
    """Module-level names that hold a path INSIDE the repository (derived from __file__)."""
    rooted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id not in rooted:
                src = ast.dump(node.value)
                if "'__file__'" in src or any(f"id='{r}'" in src for r in rooted):
                    rooted.add(node.targets[0].id)
                    changed = True
    return rooted


def _roots_in(expr: ast.AST, rooted: set[str]) -> bool:
    """Is `expr` a path built on a repo-rooted name (`ROOT / "src" / "x.py"`)?"""
    while isinstance(expr, ast.BinOp):
        expr = expr.left
    return isinstance(expr, ast.Name) and expr.id in rooted


def writes_into_the_tree(source: str) -> list[int]:
    tree = ast.parse(source)
    rooted = _rooted_names(tree)
    lines = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name) and isinstance(n.value, ast.BinOp)
                 and _roots_in(n.value, rooted)}
        for n in ast.walk(fn):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in _WRITES and (
                    (isinstance(f.value, ast.Name) and f.value.id in local)
                    or _roots_in(f.value, rooted)):
                lines.append(n.lineno)
            name = getattr(f, "attr", None) or getattr(f, "id", None)
            if name in _TEMP_FACTORIES and any(
                    k.arg == "dir" and (_roots_in(k.value, rooted)
                                        or (isinstance(k.value, ast.Name) and k.value.id in rooted))
                    for k in n.keywords):
                lines.append(n.lineno)
    return sorted(set(lines))


def test_no_test_writes_a_probe_into_the_real_tree() -> None:
    offenders = []
    for path in sorted(_TESTS.glob("test_*.py")):
        if path.name in _DECLARED:
            continue
        hits = writes_into_the_tree(path.read_text(encoding="utf-8"))
        offenders += [f"{path.name}:{ln}" for ln in hits]
    assert not offenders, (
        f"{offenders} write into the repository. Under xdist another test scanning that "
        "directory lists the file and loses it (FileNotFoundError), or counts it. Write "
        "the probe under `tmp_path` and pass the directory to the detector.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The exact shapes of 2026-09-25/26, and their corrected forms."""
    defect = (
        "import pathlib, tempfile\n"
        "_ROOT = pathlib.Path(__file__).resolve().parents[1]\n"
        "_DASH = _ROOT / 'src' / 'dashboard'\n"
        "def test_a():\n"
        "    sonde = _DASH / '_probe.py'\n"
        "    sonde.write_text('x')\n"
        "    sonde.unlink()\n"
        "def test_b():\n"
        "    tempfile.NamedTemporaryFile('w', suffix='.py', dir=_ROOT, delete=False)\n")
    assert writes_into_the_tree(defect) == [6, 7, 9]
    fixed = (
        "import pathlib, tempfile\n"
        "_ROOT = pathlib.Path(__file__).resolve().parents[1]\n"
        "def test_a(tmp_path):\n"
        "    sonde = tmp_path / '_probe.py'\n"
        "    sonde.write_text('x')\n"
        "    (_ROOT / 'src' / 'x.py').read_text()\n"
        "    tempfile.NamedTemporaryFile('w', suffix='.py', delete=False)\n")
    assert writes_into_the_tree(fixed) == []
