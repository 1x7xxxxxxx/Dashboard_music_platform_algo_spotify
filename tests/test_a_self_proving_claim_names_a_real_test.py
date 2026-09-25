"""`seen_red: self-proving (<file>::<test>)` names a test that EXISTS, in a file that exists.

Type: Sub
Uses: .claude/dev-docs/error-classes.md, tests/*.py (AST)
Depends on: nothing

`self-proving` is the strongest proof the catalogue accepts, and `make error-health` counts it
as a paid debt (R169). Nothing checked that the test it names was real: renaming or deleting the
test would have kept the class counted as proven, with no proof left anywhere — a prose claim
that cannot be verified, on the one field meant to be the verification (2026-09-26).
"""
import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CATALOGUE = _ROOT / ".claude/dev-docs/error-classes.md"
_CLAIM = re.compile(r"^- seen_red:\s*self-proving \(([^)]*)\)", re.M)
_REF = re.compile(r"(tests/[\w./-]+\.py)::(\w+)")


def dangling(catalogue: str, root: Path) -> list[str]:
    out = []
    for claim in _CLAIM.finditer(catalogue):
        refs = _REF.findall(claim.group(1))
        if not refs:
            out.append(f"no <file>::<test> in « {claim.group(1)[:60]} »")
        for rel, name in refs:
            path = root / rel
            if not path.is_file():
                out.append(f"{rel} does not exist")
                continue
            names = {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            if name not in names:
                out.append(f"{rel}::{name} does not exist")
    return out


def test_every_self_proving_claim_names_a_real_test() -> None:
    bad = dangling(_CATALOGUE.read_text(encoding="utf-8"), _ROOT)
    assert not bad, (f"{len(bad)} `self-proving` claim(s) point at nothing — the class is "
                     f"counted as proven with no proof left: {bad}")


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_g.py").write_text("def test_real():\n    pass\n", encoding="utf-8")
    ok = "- seen_red: self-proving (tests/test_g.py::test_real) — x\n"
    assert dangling(ok, tmp_path) == []
    assert dangling(ok.replace("test_real)", "test_renamed)"), tmp_path) == \
        ["tests/test_g.py::test_renamed does not exist"]
    assert dangling(ok.replace("test_g.py", "test_gone.py"), tmp_path) == \
        ["tests/test_gone.py does not exist"]
    assert dangling("- seen_red: self-proving (the guard fabricates it)\n", tmp_path)
