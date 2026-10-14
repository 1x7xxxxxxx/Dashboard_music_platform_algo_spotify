"""R563 — `make roadmap-close` says a green closure in a few lines, a red one in full.

Type: Guard
Uses: tools/dev/run_readers.py (main, subprocess stubbed), tools/dev/roadmap.py (source)
Depends on: nothing
Persists in: nothing

Six of the last ten `guard_destructive` refusals « est tubé dans » were a closure piped into
`| tail` before `&& git push`: the readers' full pytest output made the gesture long enough
to be cut. Green now prints one line; red still prints everything — a short red is a hidden
red.
"""
from __future__ import annotations

import ast
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_readers_short",
                                               ROOT / "tools/dev/run_readers.py")
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

_NOISE = "\n".join(["created: 4/4 workers", "4 workers [12 items]", "." * 12, ""] * 5)


def _stub(monkeypatch, rc: int, tail: str) -> None:
    monkeypatch.setattr(rr, "readers", lambda files: ["tests/test_a.py", "tests/test_b.py"])
    monkeypatch.setattr(rr, "_workers", lambda: "2")
    monkeypatch.setattr(rr.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, rc, stdout=_NOISE + tail + "\n", stderr=""))


def test_a_green_run_is_one_line_with_its_summary(monkeypatch, capsys) -> None:
    _stub(monkeypatch, 0, "12 passed in 3.1s")
    assert rr.main(["x.md"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 1 and out[0].endswith("12 passed in 3.1s"), out


def test_a_red_run_shows_the_whole_output(monkeypatch, capsys) -> None:
    _stub(monkeypatch, 1, "FAILED tests/test_a.py::test_x - boom\n1 failed, 11 passed")
    assert rr.main(["x.md"]) == 1
    cap = capsys.readouterr()
    assert "FAILED tests/test_a.py::test_x - boom" in cap.out and "R361" in cap.err


def _cmd_close() -> ast.FunctionDef:
    tree = ast.parse((ROOT / "tools/dev/roadmap.py").read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cmd_close")


def _is_print(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "print")


def test_the_closure_itself_prints_one_line_under_make() -> None:
    body = _cmd_close().body
    written = next(i for i, st in enumerate(body)
                   if any(isinstance(c, ast.Attribute) and c.attr == "write_text"
                          and isinstance(c.value, ast.Name) and c.value.id == "CHECKLIST"
                          for c in ast.walk(st)))
    tail = body[written + 1:]
    assert sum(_is_print(st) for st in tail) == 1, [ast.unparse(st) for st in tail if _is_print(st)]
    gated = [st for st in tail if isinstance(st, ast.If) and "MAKELEVEL" in ast.unparse(st.test)
             and all(_is_print(b) for b in st.body)]
    assert gated, "the « vérifier » hint must be printed only outside make"
