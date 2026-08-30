"""`tenant_scope()` and `view_session()` disagree about admins. Do not "unify" them.

Type: Test
Uses: ast
Depends on: src/dashboard/views/*.py, src/dashboard/auth.py, src/dashboard/utils/__init__.py
Persists in: nothing

What this stops
---------------
Rule #9 and roadmap item R9 both read as "migrate the remaining views to
`view_session()`", and a mechanical sweep is the obvious way to close them. Measured
on 2026-08-30, that sweep would have been a tenant leak.

Of the 25 views not using `view_session()`:

    17   never call get_artist_id() at all — they use `tenant_scope()`
     8   have no admin fallback, i.e. a different semantic
     1   (hypeddit) actually matches the legacy shape view_session replaces

The two helpers answer the same question with **opposite** answers for an admin:

    view_session()   admin with no artist  ->  artist_id = 1   (see its docstring)
    tenant_scope()   admin with no artist  ->  None            ("never a stray artist")

`home.py:246` spells the intent in a comment: `# None = admin only, never a stray
artist`. Rewriting those 17 views to `view_session()` would silently hand every
admin the data of artist 1 — which is the exact shape of the leak that took two
failed artist-test sessions to find, where `track_popularity_history` stored every
tenant's history under the admin for months.

So this is not a style choice with a winner. It is two behaviours, and the guard
exists so that the next person reading "migrate the remaining views" reads this
first.

Why a test and not a comment
----------------------------
Because a comment in `CLAUDE.md` did not prevent the Views Map from drifting twice,
and a warning sentence has never stopped a sweep. The assertion below fails the
moment a `tenant_scope()` view also imports `view_session`.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"
_AUTH = _ROOT / "src" / "dashboard" / "auth.py"
_UTILS = _ROOT / "src" / "dashboard" / "utils" / "__init__.py"


def _imported_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            out |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            out |= {(a.asname or a.name).split(".")[0] for a in node.names}
    return out


def views_mixing_both_tenant_helpers(paths: list[Path] | None = None) -> list[str]:
    """Views that pull in BOTH helpers — the shape a mechanical sweep leaves behind.

    Takes an explicit path list so the mutation test can hand it a fixture, rather
    than rebinding a module global. The first draft did rebind, and it failed on
    `Path.relative_to` for a file outside the repo — a test that breaks on its own
    plumbing teaches nothing about the code.
    """
    bad = []
    for path in sorted(paths if paths is not None else _VIEWS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        names = _imported_names(tree)
        if "tenant_scope" in names and "view_session" in names:
            try:
                bad.append(str(path.relative_to(_ROOT)))
            except ValueError:
                bad.append(str(path))
    return bad


def test_no_view_imports_both_tenant_helpers():
    offenders = views_mixing_both_tenant_helpers()
    assert not offenders, (
        "These views import both `tenant_scope` and `view_session`:\n  "
        + "\n  ".join(offenders)
        + "\n\nThey disagree about admins — tenant_scope gives None, view_session "
          "gives artist_id = 1. A view that holds both is one edit away from handing "
          "an admin artist 1's data. Pick the one the view's semantics require."
    )


def test_the_two_helpers_really_do_disagree_about_admins():
    """Pin the behaviour this guard is protecting, read from the source.

    If someone ever makes them agree, this test should be the thing that notices —
    and then the guard above can be retired on purpose rather than by accident.
    """
    utils = _UTILS.read_text(encoding="utf-8")
    tree = ast.parse(utils)
    vs = next((f for f in ast.walk(tree)
               if isinstance(f, ast.FunctionDef) and f.name == "view_session"), None)
    assert vs is not None, "view_session() is gone from utils/__init__.py"
    body = ast.get_source_segment(utils, vs) or ""
    assert "artist_id = 1" in body, (
        "view_session() no longer falls back to artist_id = 1 for admins. If that is "
        "deliberate, the 17 tenant_scope views may finally be migratable — re-read "
        "this file before doing it."
    )

    auth = _AUTH.read_text(encoding="utf-8")
    atree = ast.parse(auth)
    ts = next((f for f in ast.walk(atree)
               if isinstance(f, ast.FunctionDef) and f.name == "tenant_scope"), None)
    assert ts is not None, "tenant_scope() is gone from auth.py"
    ts_body = ast.get_source_segment(auth, ts) or ""
    assert "None" in ts_body, (
        "tenant_scope() no longer has a None path — its whole point was that an admin "
        "gets no tenant rather than a stray one."
    )


def test_the_guard_goes_red_on_a_view_that_holds_both(tmp_path):
    """Mutation: the exact shape a mechanical migration would produce."""
    swept = tmp_path / "swept.py"
    swept.write_text(
        "from src.dashboard.auth import tenant_scope\n"
        "from src.dashboard.utils import view_session\n"
        "def show():\n"
        "    with view_session() as (db, artist_id):\n"
        "        pass\n", encoding="utf-8")
    assert views_mixing_both_tenant_helpers([swept]), (
        "the guard does not see a view holding both helpers"
    )

    only_one = tmp_path / "fine.py"
    only_one.write_text(
        "from src.dashboard.auth import tenant_scope\n"
        "def show():\n"
        "    aid = tenant_scope()\n", encoding="utf-8")
    assert views_mixing_both_tenant_helpers([only_one]) == []
