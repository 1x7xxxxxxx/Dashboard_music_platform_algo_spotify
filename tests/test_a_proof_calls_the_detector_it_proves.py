"""A self-proving test must CALL the detector it proves — never a copy of it.

Type: Sub
Uses: ast, tests/test_*.py
Depends on: nothing
Persists in: nothing

Measured 2026-09-26 (R169). `test_a_shared_path_does_not_drag_a_view_behind_it.py`
carried a non-vacuity test that rebuilt the predicate inline (`[n for n in ast.walk(tree)
if isinstance(n, ast.ImportFrom) and ".views." in …]`) instead of calling `_view_imports`.
Making the REAL predicate blind to lazy imports — the exact defect the file exists for —
left the proof green. A proof over a copy proves the copy.

Sweep the same day (rule 20 funnel): 19 proofs referenced no helper by a naive predicate
→ 18 called through a module alias (`import x as mod`, `mod.frozen(...)`) → 1 called the
guard's own `test_*` checks → 0 live sites beyond the fixed one. This guard keeps it at 0.

Does NOT cover: a proof under ANOTHER name — the 2026-09-26 one was called
`test_the_predicate_sees_the_lazy_form`, and this guard reads only the canonical name
(renamed when fixed). Nor a proof that calls a helper AND rebuilds the predicate beside it.
"""
from __future__ import annotations

import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_PROOF = "test_the_detector_sees_the_defect_it_is_written_for"
_STDLIB_NOISE = {"pytest", "ast", "re", "json", "os", "sys", "Path", "pathlib",
                 "subprocess", "textwrap", "annotations"}


def _module_names(tree: ast.Module) -> set[str]:
    """Names the module defines or imports — the only things a proof can be ABOUT."""
    out: set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.ImportFrom):
            out |= {a.asname or a.name for a in n.names}
        elif isinstance(n, ast.Import):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    return out - _STDLIB_NOISE - {_PROOF}


def proofs_over_a_copy(source: str) -> list[int]:
    """Lines of proofs that touch nothing the module defines or imports. Pure."""
    tree = ast.parse(source)
    known = _module_names(tree)
    hits = []
    for fn in tree.body:
        if not (isinstance(fn, ast.FunctionDef) and fn.name == _PROOF):
            continue
        if any(isinstance(n, ast.ImportFrom) for n in ast.walk(fn)):
            continue                      # imports the detector locally: it calls it
        used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        if not used & known:
            hits.append(fn.lineno)
    return hits


def test_every_proof_calls_what_it_proves() -> None:
    offenders = [f"{p.name}:{line}" for p in sorted(_TESTS.glob("test_*.py"))
                 for line in proofs_over_a_copy(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        f"{offenders}: `{_PROOF}` references nothing the module defines or imports — "
        "it proves a copy of the predicate, not the predicate. Break the real one and "
        "this proof stays green. Extract the predicate into a function and call it "
        "from BOTH the guard and the proof.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the 2026-09-26 shape (predicate rebuilt inline) is named; a proof
    calling the module's helper, a module alias, or a local import is not."""
    copy = ("import ast\n"
            "def _view_imports():\n    return []\n"
            f"def {_PROOF}():\n"
            "    tree = ast.parse('from a.views.b import c')\n"
            "    assert [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]\n")
    assert proofs_over_a_copy(copy) == [4]
    calls = copy.replace("    assert [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]\n",
                         "    assert _view_imports() == []\n")
    assert proofs_over_a_copy(calls) == []
    alias = f"import tools.dev.x as mod\ndef {_PROOF}():\n    assert mod.frozen({{}}, {{}})\n"
    assert proofs_over_a_copy(alias) == []
    local = f"def {_PROOF}():\n    from tools.x import f\n    assert f()\n"
    assert proofs_over_a_copy(local) == []
