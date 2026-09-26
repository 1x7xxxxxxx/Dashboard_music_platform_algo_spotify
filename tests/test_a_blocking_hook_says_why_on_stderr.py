"""A hook that BLOCKS says why on stderr — the only channel relayed on exit 2.

Type: Sub
Uses: .claude/hooks/*.py (read as AST)
Depends on: nothing
Persists in: nothing

Class `a-blocking-hook-that-writes-its-reason-to-stdout`: the Claude Code hook contract
is "exit 2 blocks, and STDERR carries the reason to the model". `pre_commit_scan.py`
printed its « 🚫 BLOCKED » block with a bare `print()`, so the door closed without a
word. The class signature only asked whether ONE print of that hook went to stderr,
and its `guard_scope` named the neighbour hooks as uncovered. This file asks every hook:
a function that can end in a 2 (a `return 2`, a conditional `return 2 if …`, a
`sys.exit(2)`, a `SystemExit(2)`) prints nothing to stdout.
"""
from __future__ import annotations

import ast
from pathlib import Path

_HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"


def _is_two(node) -> bool:
    if isinstance(node, ast.Constant):
        return node.value == 2
    if isinstance(node, ast.IfExp):
        return _is_two(node.body) or _is_two(node.orelse)
    return False


def _blocks(stmt: ast.stmt) -> bool:
    """Is THIS statement the blocking exit: `return 2` (or `return 2 if … else …`),
    `sys.exit(2)`, `exit(2)`, `raise SystemExit(2)`?"""
    if isinstance(stmt, ast.Return):
        return stmt.value is not None and _is_two(stmt.value)
    call = (stmt.value if isinstance(stmt, ast.Expr)
            else stmt.exc if isinstance(stmt, ast.Raise) else None)
    return (isinstance(call, ast.Call) and bool(call.args) and _is_two(call.args[0])
            and (getattr(call.func, "attr", "") == "exit"
                 or getattr(call.func, "id", "") in ("exit", "SystemExit")))


def _to_stderr(call: ast.Call) -> bool:
    return any(k.arg == "file" and getattr(k.value, "attr", "") == "stderr"
               for k in call.keywords)


def silent_blocking_prints(source: str) -> list[int]:
    """Line of every stdout `print` that runs BEFORE a blocking exit of the same block
    — the reason the door gives, written where it is swallowed. A warning printed on a
    path that ends in 0 is not one (the first, function-wide version of this predicate
    named two such warnings: 5 candidates, 2 discarded, 3 live). Pure."""
    out = []
    for node in ast.walk(ast.parse(source)):
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field, None)
            if not isinstance(stmts, list):
                continue
            for i, stmt in enumerate(stmts):
                if not _blocks(stmt):
                    continue
                out += [c.lineno for before in stmts[:i] for c in ast.walk(before)
                        if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "print"
                        and not _to_stderr(c)]
    return sorted(set(out))


def test_no_blocking_hook_speaks_on_stdout() -> None:
    hooks = sorted(_HOOKS.glob("*.py"))
    assert len(hooks) > 5, "the hooks folder is nearly empty — the scan sees nothing"
    offenders = [f"{p.name}:{hit}" for p in hooks
                 for hit in silent_blocking_prints(p.read_text(encoding="utf-8-sig"))]
    assert not offenders, (
        f"{offenders} : ces `print` vont sur STDOUT dans une fonction qui peut rendre 2. "
        "Sur exit 2, Claude Code ne relaie que STDERR au modèle : la porte se ferme sans "
        "dire pourquoi. `print(..., file=sys.stderr)`.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the scanner of before 2026-09-16 (bare `print` then
    `sys.exit(2)`), a helper that prints then `return 2 if … else 0`, and a
    `raise SystemExit(2)` after a bare print are named; the same code writing to
    `sys.stderr`, and a warning printed on a branch that exits 0, are not."""
    old = ("def main():\n    print('🚫 BLOCKED — secret')\n    sys.exit(2)\n")
    helper = ("def run_ruff(f):\n    print(f'Syntax error in {f}')\n"
              "    return 2 if bad else 0\n")
    raised = ("def gate():\n    print('refused')\n    raise SystemExit(2)\n")
    assert silent_blocking_prints(old) == [2]
    assert silent_blocking_prints(helper) == [2]
    assert silent_blocking_prints(raised) == [2]
    fixed = old.replace("print('🚫 BLOCKED — secret')",
                        "print('🚫 BLOCKED — secret', file=sys.stderr)")
    # guard_destructive's shape: block on stderr, WARN on stdout and exit 0.
    warn = ("def main():\n    if level == 'block':\n"
            "        print('🚫', file=sys.stderr)\n        sys.exit(2)\n"
            "    else:\n        print('⚠️ risky')\n        sys.exit(0)\n")
    assert silent_blocking_prints(fixed) == []
    assert silent_blocking_prints(warn) == []
