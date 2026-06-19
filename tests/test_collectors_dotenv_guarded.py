"""Guard: collectors must not crash at import on an unreadable .env.

Type: Utility
Error class `collector-import-dotenv-crash`. Benken incident 2026-06-19: a module-level
`load_dotenv()` in a collector raised PermissionError at import because prod's mounted
/opt/airflow/.env is root-owned 600 (unreadable by the airflow uid). The env is already
injected by docker-compose, so any `load_dotenv()` in a collector MUST be wrapped in
try/except so an unreadable/absent .env is a no-op, never fatal.
"""
import ast
from pathlib import Path

import pytest

_COLLECTORS = sorted((Path(__file__).resolve().parent.parent / "src" / "collectors").glob("*.py"))


def _module_level_load_dotenv_calls(tree: ast.AST):
    """Yield Call nodes for top-level (module body) load_dotenv(...) — NOT inside a Try."""
    for node in tree.body:  # module-level statements only
        if isinstance(node, ast.Try):
            continue  # guarded — fine
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                fn = call.func
                if isinstance(fn, ast.Name) and fn.id == "load_dotenv":
                    yield call


@pytest.mark.parametrize("collector", _COLLECTORS, ids=lambda p: p.name)
def test_no_unguarded_load_dotenv(collector):
    tree = ast.parse(collector.read_text(encoding="utf-8-sig"))
    unguarded = [c.lineno for c in _module_level_load_dotenv_calls(tree)]
    assert not unguarded, (
        f"{collector.name}: module-level load_dotenv() at line(s) {unguarded} is not wrapped "
        "in try/except — it will crash the collector at import if /opt/airflow/.env is "
        "unreadable. Wrap it like soundcloud_api_collector.py (try/except OSError)."
    )
