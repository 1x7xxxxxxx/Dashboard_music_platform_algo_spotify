"""Guard — a tenant's IDENTITY never falls back to the environment.

Error class `tenant-identity-falls-back-to-admin`.

The environment carries the ADMIN's identity. `x or os.getenv("...")` on an identity
therefore means: a tenant who left the field blank silently collects the admin's
account, and the rows are filed under the tenant. That is how
`track_popularity_history` filed every tenant's history under artist 1 for months
without a single error.

App credentials (a shared client id, a shared token) may fall back to the env — that
is the central-app model, ADR-006. Identities may not. This guard knows the
difference by name.

**AST, not grep, and that is not a preference.** The words `INSTAGRAM_USER_ID` and
`SOUNDCLOUD_USER_ID` appear in the explanatory comments of the very files checked
here — comments that exist to say why the fallback was removed. A textual signature
would be permanently red on the documentation of its own fix, and the only way to
keep CI green would be to stop explaining.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Env vars that name a TENANT's identity. A fallback onto any of these is the defect.
# App-credential env vars (tokens, client ids, secrets) are deliberately absent.
_IDENTITY_ENV = {
    "INSTAGRAM_USER_ID",
    "SOUNDCLOUD_USER_ID",
    "YOUTUBE_CHANNEL_ID",
    "META_ACCOUNT_ID",
    "SPOTIFY_ARTIST_ID",
    "SPOTIFY_ARTIST_IDS",
}

# Single-tenant by design: these scripts exist to run one artist from a shell.
_EXEMPT_DIRS = ("airflow/debug_dag",)


def _sources() -> list[Path]:
    out: list[Path] = []
    for sub in ("src/collectors", "src/utils", "airflow/dags"):
        for p in (ROOT / sub).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if any(rel.startswith(d) for d in _EXEMPT_DIRS):
                continue
            out.append(p)
    return sorted(out)


def _getenv_identity_names(call: ast.Call) -> set[str]:
    fn = call.func
    is_getenv = (
        (isinstance(fn, ast.Attribute) and fn.attr == "getenv")
        or (isinstance(fn, ast.Name) and fn.id == "getenv")
    )
    if not is_getenv or not call.args:
        return set()
    first = call.args[0]
    if isinstance(first, ast.Constant) and first.value in _IDENTITY_ENV:
        return {first.value}
    return set()


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.name)
def test_no_identity_is_read_from_the_environment_as_a_fallback(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offences = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        for value in node.values:
            for inner in ast.walk(value):
                if isinstance(inner, ast.Call):
                    for name in _getenv_identity_names(inner):
                        offences.append((name, node.lineno))
    assert not offences, (
        f"{path.relative_to(ROOT)} falls back to a tenant identity from the "
        f"environment: {offences}. The env holds the ADMIN's identity — a tenant "
        f"with a blank field would collect the admin's account under its own name."
    )


def test_the_guard_would_actually_catch_the_shape_it_describes() -> None:
    """A guard never seen red keeps nothing. Prove the detector on a synthetic case."""
    src = 'import os\nx = ig_user_id or os.getenv("INSTAGRAM_USER_ID") or ""\n'
    tree = ast.parse(src)
    found = [
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)
        for value in node.values
        for inner in ast.walk(value)
        if isinstance(inner, ast.Call)
        for name in _getenv_identity_names(inner)
    ]
    assert found == ["INSTAGRAM_USER_ID"]


def test_the_exact_comment_that_would_break_a_grep_is_present() -> None:
    """Pins WHY this file is AST-based, so nobody 'simplifies' it back to a grep."""
    text = (ROOT / "src/collectors/instagram_api_collector.py").read_text(encoding="utf-8")
    assert "INSTAGRAM_USER_ID" in text, (
        "the explanatory comment naming the removed env var is gone — with it goes "
        "the reason this guard reads the AST instead of the file text"
    )
