"""The API has ONE version, and the running app reports it (R621).

Type: Hook
Uses: src/api/__init__.py (`__version__`), src/api/main.py, pyproject.toml
Persists in: nothing

Measured on 2026-10-15: `pyproject.toml` said 0.1.0 while `FastAPI(version="1.0.0")` told
/openapi.json readers a stability contract nobody had asked for. Zero external consumers
in 30 days of prod logs, so the decision was one true version and no CHANGELOG / `/v1`.

guard_scope: the `version=` keyword of any call under src/api/ given a string literal,
and the pyproject ↔ `__version__` pair. NOT covered: a version written in prose (README,
docs), a `version` built by concatenation.
"""
from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _literal_versions(source: str) -> list[int]:
    """Lines where a call passes `version=<string literal>`."""
    return [kw.value.lineno for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) for kw in node.keywords
            if kw.arg == "version" and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)]


def test_pyproject_and_the_api_carry_the_same_version() -> None:
    from src.api import __version__
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__


def test_no_other_version_literal_under_src_api() -> None:
    hits = [f"{p.relative_to(ROOT)}:{line}" for p in sorted((ROOT / "src" / "api").rglob("*.py"))
            for line in _literal_versions(p.read_text(encoding="utf-8"))]
    assert not hits, f"a second version literal — use src.api.__version__: {hits}"


def test_the_detector_sees_a_literal_and_not_a_name() -> None:
    assert _literal_versions('FastAPI(title="x", version="1.0.0")\n') == [1]
    assert _literal_versions("FastAPI(version=__version__)\n'version=\"1.0.0\"'\n") == []


def test_the_running_app_reports_it() -> None:
    from src.api import __version__
    from src.api.main import app
    assert app.version == __version__
