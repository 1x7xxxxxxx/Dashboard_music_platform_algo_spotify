"""A rate limiter is never read and then written in two steps by its callers.

Type: Sub
Uses: src/ (read as AST)
Depends on: nothing
Persists in: nothing

Class `a-limiter-consumed-in-two-steps`: `throttle.py` serialises `DELETE / count /
INSERT` under an advisory lock, but `auth.py` called `throttle_check()` (which does NOT
consume), verified the TOTP code, then `throttle_record()` only on failure — all the work
between the read and the write is a window for a parallel session. The fix is
`throttle_consume()`, which decides and consumes at once. `throttle_record` may only be
called by `throttle.py` itself.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_HOME = "throttle.py"


def split_consumers(source: str) -> list[int]:
    """Lines that CALL `throttle_record` (bare or as an attribute). Comments and
    docstrings are not calls. Pure."""
    return sorted(n.lineno for n in ast.walk(ast.parse(source))
                  if isinstance(n, ast.Call)
                  and (getattr(n.func, "id", None) == "throttle_record"
                       or getattr(n.func, "attr", None) == "throttle_record"))


def test_no_caller_records_a_limit_after_checking_it() -> None:
    offenders = []
    for p in sorted((_ROOT / "src").rglob("*.py")):
        if p.name == _HOME or "__pycache__" in p.parts:
            continue
        offenders += [f"{p.relative_to(_ROOT).as_posix()}:{line}"
                      for line in split_consumers(p.read_text(encoding="utf-8-sig"))]
    assert not offenders, (
        f"{offenders} : `throttle_record()` appelé hors de `throttle.py`. Lire la limite "
        "puis l'écrire en deux temps laisse une session parallèle passer entre les deux. "
        "Appeler `throttle_consume()`, qui décide et consomme d'un seul geste.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the 2026-09-16 login — check, verify, record on failure — is named,
    bare or through the module; a caller of `throttle_consume`, and a comment or a
    docstring naming `throttle_record`, are not."""
    two_steps = ("def login(u, code):\n"
                 "    if throttle_check('totp', u):\n        return False\n"
                 "    if not verify(code):\n        throttle_record('totp', u)\n"
                 "        throttle.throttle_record('totp', u)\n")
    assert split_consumers(two_steps) == [5, 6]
    one_step = ('def login(u, code):\n    """Never throttle_record() here."""\n'
                "    # throttle_record('totp', u) was the defect\n"
                "    if throttle_consume('totp', u):\n        return False\n")
    assert split_consumers(one_step) == []
