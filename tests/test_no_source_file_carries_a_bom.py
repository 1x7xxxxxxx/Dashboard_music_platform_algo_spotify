"""No Python file of the repo starts with a UTF-8 BOM.

Type: Sub
Uses: src/, airflow/, tests/, .claude/scripts/ (read as bytes)
Depends on: nothing
Persists in: nothing

Class `ast-guard-blind-to-bom`: files edited on Windows acquire a BOM; the interpreter
strips it, but `ast.parse` on an already-decoded string does not — and a guard that
catches `SyntaxError` and moves on turns the blind spot into a pass. The class
signature was a one-line `python3 -c`; this file asks the same question and proves it.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCOPE = ("src", "airflow", "tests", ".claude/scripts", ".claude/hooks", "tools")
_BOM = b"\xef\xbb\xbf"


def bom_files(files: dict[str, bytes]) -> list[str]:
    """Names whose content starts with a UTF-8 BOM. Pure."""
    return sorted(name for name, head in files.items() if head.startswith(_BOM))


def test_no_python_file_starts_with_a_bom() -> None:
    heads = {p.relative_to(_ROOT).as_posix(): p.read_bytes()[:3]
             for d in _SCOPE for p in (_ROOT / d).rglob("*.py")
             if "__pycache__" not in p.parts}
    assert len(heads) > 500, "the scan reached almost nothing — check the scope"
    bad = bom_files(heads)
    assert not bad, (
        f"{bad} commencent par un BOM UTF-8. L'interpréteur le tolère, `ast.parse` sur "
        "une chaîne décodée non : chaque garde AST qui avale `SyntaxError` passe ces "
        "fichiers sans les lire. Réenregistrer en UTF-8 sans BOM.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: a file saved by a Windows editor (BOM first) is named; the same
    code without it, and a BOM that is NOT at the start (a literal in the text), are
    not."""
    code = b"import os\n"
    files = {"win.py": _BOM + code, "clean.py": code, "literal.py": b"x = '" + _BOM + b"'\n"}
    assert bom_files(files) == ["win.py"]
