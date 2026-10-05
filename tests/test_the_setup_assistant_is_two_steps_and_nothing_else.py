"""The setup assistant is its two steps, and nothing else around them.

Type: Hook
Uses: ast over src/dashboard/app.py and src/dashboard/views/onboarding.py
Depends on: nothing (no database)
Persists in: nothing

R347 (2026-10-04, owner's screen review): « On avait dit qu'on devait aller directement
avec deux choix, Bienvenue et Choix, et le 2, où tu en es. Et là on peut voir toute
l'app » — and « Connecter mes sources … ça va directement dans Credential API. Mais
normalement ça va sur Où tu en es ». Three properties, one test each:

1. on the assistant page the sidebar carries the steps and no navigation, for EVERY
   account — the bare sidebar was reserved to the first login (`FIRST_RUN_FOCUS`), so a
   configured artist who opened the assistant saw the whole app beside it;
2. « Connecter mes sources » on step 1 goes to step 2, it does not leave the assistant;
3. the welcome block keeps only « streaMLytics en bref » + its one sentence.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "dashboard" / "app.py"
ONB = ROOT / "src" / "dashboard" / "views" / "onboarding.py"


def _fn(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name)


def bare_depends_on_first_run(fn: ast.FunctionDef,
                              helper: ast.FunctionDef | None = None) -> bool | None:
    """Does the `_bare` decision read the first-run flag? None if `_bare` is gone. Pure.

    Since 2026-10-04 `_bare` is computed by `sidebar_is_bare(page)`: when the assigned
    value is a call to `helper`, the helper's body is what is read.
    """
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "_bare"
                                              for t in n.targets)):
            value: ast.AST = n.value
            if (helper is not None and isinstance(value, ast.Call)
                    and getattr(value.func, "id", "") == helper.name):
                value = helper
            names = {x.id for x in ast.walk(value) if isinstance(x, ast.Name)}
            consts = {x.value for x in ast.walk(value) if isinstance(x, ast.Constant)}
            assert "onboarding" in consts, "`_bare` no longer names the assistant page"
            return "FIRST_RUN_FOCUS" in names or "_focus" in names
    return None


def test_the_assistant_sidebar_is_bare_for_every_account() -> None:
    found = bare_depends_on_first_run(_fn(APP, "_main_body"),
                                      _fn(APP, "sidebar_is_bare"))
    assert found is not None, "the `_bare` decision disappeared from `_main_body`"
    assert not found, (
        "the bare sidebar on the assistant depends on the FIRST login again: a configured "
        "artist who opens « Mise en route » sees the whole menu beside the two steps (R347).")


def _welcome_button_body(fn: ast.FunctionDef) -> list[ast.stmt]:
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Call):
            keys = [k.value.value for k in n.test.keywords
                    if k.arg == "key" and isinstance(k.value, ast.Constant)]
            if keys == ["_onb_go_creds"]:
                return n.body
    raise AssertionError("the « Connecter mes sources » button of step 1 is gone")


def test_connect_my_sources_goes_to_step_two() -> None:
    body = _welcome_button_body(_fn(ONB, "_step_welcome"))
    sets_two = any(isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)
                   and s.value.value == 2
                   and any(getattr(getattr(t, "slice", None), "id", "") == "_STEP_KEY"
                           for t in s.targets)
                   for s in body)
    leaves = [c for s in body for c in ast.walk(s) if isinstance(c, ast.Call)
              and getattr(c.func, "id", "") in {"_goto", "goto"}]
    assert sets_two and not leaves, (
        "« Connecter mes sources » must set the step to 2 (« Où tu en es ») and stay on the "
        "assistant; it led straight to Credentials (R347).")


def _strings_and_names(path: Path) -> set[str]:
    """Every string constant, name and function name of a module. Pure."""
    out: set[str] = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
        elif isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.FunctionDef):
            out.add(n.name)
    return out


def test_the_welcome_block_is_one_sentence() -> None:
    seen = _strings_and_names(ONB)
    # R374 brought the figures back as GENERIC examples (shared module, no tenant data —
    # tests/test_the_welcome_figures_are_examples.py); the long filler sentences stay out.
    back = {"onboarding.brief_2", "onboarding.brief_3", "_example_chart"} & seen
    assert not back, f"{back} is back in the welcome step (R347: no filler)"
    assert "onboarding.brief_1" in seen, "the one sentence that stays is gone too"
