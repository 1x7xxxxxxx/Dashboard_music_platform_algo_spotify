"""Guard: every `PostgresHandler(...)` call site can actually bind the constructor.

Type: Utility
Uses: ast, inspect, src.database.postgres_handler
Triggers: pytest
Persists in: nothing

Error class `handler-built-without-its-arguments`.

Measured 2026-08-28. `alert_monitor._mirrored_identities` shipped on 2026-08-26 with
`db = PostgresHandler()`. `__init__` takes five required positional arguments, so the
call could only ever raise `TypeError`. Nothing said so until 01:00, twice:

    TypeError: PostgresHandler.__init__() missing 5 required positional arguments:
    'host', 'port', 'database', 'user', and 'password'

Two nights of `check_credentials_all` produced nothing — the credential audit was blind
while looking green enough that only the failure mail revealed it.

Why an AST guard and not a text search: the same file holds nine correct call sites and
the strings `PostgresHandler(` and `PostgresHandler()` both appear inside comments and
docstrings — including the ones written for this very fix. A grep would either miss the
defect or trip over the prose explaining it (the lesson of 2026-08-22, four guards that
matched their own comment).

Why it reads `inspect.signature` instead of hard-coding five names: a guard that pins
today's parameter list starts lying the day the constructor changes. Binding against the
real signature keeps the question — *can this call succeed?* — instead of the symptom.
"""
import ast
import inspect
from pathlib import Path

import pytest

from src.database.postgres_handler import PostgresHandler

_ROOT = Path(__file__).resolve().parent.parent
_TREES = ("src", "airflow", "tools")
_SIGNATURE = inspect.signature(PostgresHandler.__init__)


def _python_files():
    for tree in _TREES:
        for path in sorted((_ROOT / tree).rglob("*.py")):
            if "__pycache__" in path.parts or "venv" in path.parts:
                continue
            yield path


def _direct_construction_calls(tree: ast.AST):
    """Yield `PostgresHandler(...)` Call nodes — never `PostgresHandler.from_x(...)`.

    A classmethod door (`from_url`, `from_env_or_config`) has its own signature and is
    not this guard's question.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == "PostgresHandler":
            yield node
        elif (isinstance(fn, ast.Attribute) and fn.attr == "PostgresHandler"):
            yield node  # `module.PostgresHandler(...)`


def _cannot_bind(call: ast.Call) -> str | None:
    """Why this call cannot bind `__init__`, or None when it binds (or is undecidable).

    A `*args` / `**kwargs` unpacking makes the argument set unknown at parse time; such
    a call is skipped rather than guessed at, and there are none today.
    """
    if any(isinstance(a, ast.Starred) for a in call.args):
        return None
    if any(kw.arg is None for kw in call.keywords):
        return None
    args = [object()] * (len(call.args) + 1)  # +1 for `self`
    kwargs = {kw.arg: object() for kw in call.keywords}
    try:
        _SIGNATURE.bind(*args, **kwargs)
    except TypeError as e:
        return str(e)
    return None


@pytest.mark.parametrize("path", list(_python_files()), ids=lambda p: str(p.relative_to(_ROOT)))
def test_every_construction_binds_the_constructor(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    broken = [
        (call.lineno, reason)
        for call in _direct_construction_calls(tree)
        if (reason := _cannot_bind(call)) is not None
    ]
    assert not broken, (
        f"{path.relative_to(_ROOT)}: PostgresHandler(...) cannot be constructed at "
        + ", ".join(f"line {lineno} ({reason})" for lineno, reason in broken)
        + ". Pass the five arguments, or use PostgresHandler.from_env_or_config() — "
        "the door that resolves DATABASE_URL, then the DATABASE_* variables, then "
        "config.yaml, and the only one that works unchanged inside Airflow."
    )


def test_the_guard_would_see_the_defect_it_was_written_for():
    """Mutation: the exact line that mailed twice must be reported by `_cannot_bind`.

    Without this, a guard that walks every file and finds nothing is indistinguishable
    from a guard whose predicate matches nothing at all.
    """
    call = ast.parse("PostgresHandler()").body[0].value
    reason = _cannot_bind(call)
    assert reason is not None and "host" in reason, reason


def test_the_guard_accepts_the_forms_production_actually_uses():
    """The two correct idioms must stay silent — a guard that flags them gets deleted."""
    five_kwargs = ast.parse(
        "PostgresHandler(host='h', port=1, database='d', user='u', password='p')"
    ).body[0].value
    assert _cannot_bind(five_kwargs) is None

    # `from_env_or_config()` is a classmethod, so it is not a construction call at all.
    tree = ast.parse("PostgresHandler.from_env_or_config()")
    assert not list(_direct_construction_calls(tree))
