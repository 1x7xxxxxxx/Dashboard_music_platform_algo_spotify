"""R462 — the referral page tells where the code is typed, by the field's real label.

Type: Test
Uses: src/dashboard/views/referral.py, src/dashboard/views/register.py (AST only)

Owner, 2026-10-07: « Ou juste le code, pour le dire à l'oral ? Comment ça le dire à
l'oral ? Le code, il faut le rentrer quelque part. » The code is typed in the sign-up
form's « Code promo ou parrainage » field; the page must name that field, and with the
label the form really shows — renaming one without the other breaks the instruction.
"""
from __future__ import annotations

import ast
from pathlib import Path

VIEWS = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"


def _default_of(module: str, key: str) -> str:
    tree = ast.parse((VIEWS / f"{module}.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "t"
                and len(node.args) == 2 and getattr(node.args[0], "value", None) == key):
            return ast.literal_eval(node.args[1])
    raise AssertionError(f"t({key!r}, …) not found in {module}.py")


def test_the_code_line_names_the_signup_field_it_is_typed_in():
    field = _default_of("register", "register.referral_code").split(" (")[0]
    line = _default_of("referral", "referral.code_alone")
    assert field in line, (field, line)
    assert "oral" not in line
