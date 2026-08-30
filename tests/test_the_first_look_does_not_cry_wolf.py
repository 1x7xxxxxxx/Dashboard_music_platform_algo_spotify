"""The tool that describes a new artist's screens must not report its own gaps.

Type: Test
Uses: ast
Depends on: tools/artist_first_look.py, src/dashboard/auth.py, src/dashboard/app.py
Persists in: nothing

Why this test exists
--------------------
`tools/artist_first_look.py` prints what a brand-new artist sees, page by page, and
flags a page with nothing to click as a DEAD END — the shape of the six defects of
2026-08-23, all of which were correct code that nothing reached.

On its first real run it reported **four** dead ends. **Three were its own fault**:

  * `account` said "Session expirée" — the harness set four of the six session keys
    a real login writes;
  * then "Utilisateur introuvable" — the throwaway tenant had a `saas_artists` row
    and no `saas_users` row, which no real signup ever produces;
  * `useful_links` said "⛔ Accès réservé à l'administrateur" — it is in
    `app._ADMIN_ONLY`, so an artist never reaches it; the journey list was wrong;
  * `process_guide` looked empty — `AppTest` exposes no `download_button`, and that
    page's only actions are two downloads.

A tool that cries wolf three times out of four is worse than no tool: its next
report gets ignored. So the properties that made it honest are pinned here.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "tools" / "artist_first_look.py"
_AUTH = _ROOT / "src" / "dashboard" / "auth.py"
_APP = _ROOT / "src" / "dashboard" / "app.py"


def _tool_source() -> str:
    return _TOOL.read_text(encoding="utf-8")


def _journey_views() -> list[str]:
    tree = ast.parse(_tool_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "JOURNEY" for t in node.targets):
            return [e.elts[0].value for e in node.value.elts]
    raise AssertionError("JOURNEY is gone from artist_first_look.py")


def _admin_only() -> set[str]:
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "_ADMIN_ONLY" for t in node.targets):
            return {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
    raise AssertionError("_ADMIN_ONLY is gone from app.py")


def test_the_journey_contains_no_admin_only_page():
    """An artist never reaches these, so a red on one is a lie about the product."""
    leaked = sorted(set(_journey_views()) & _admin_only())
    assert not leaked, (
        f"{leaked} are in app._ADMIN_ONLY — an artist never sees them. Walking them "
        "in the journey makes the tool report '⛔ Accès réservé à l'administrateur' "
        "as a defect, which is a defect of the LIST."
    )


def test_the_harness_sets_every_session_key_a_real_login_sets():
    """Model the session faithfully, or the tool reports its own gaps.

    Read from `auth.py` rather than hardcoded: when login starts writing a seventh
    key, this fails instead of the tool inventing a finding six months later.
    """
    auth = _AUTH.read_text(encoding="utf-8")
    tree = ast.parse(auth)
    real_keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "session_state"
                    and isinstance(target.slice, ast.Constant)):
                real_keys.add(target.slice.value)
    # Only the identity keys matter here; auth.py also writes navigation state.
    identity = real_keys & {"username", "name", "email", "user_id", "artist_id",
                            "role", "authenticated"}
    assert identity, "no session identity keys found in auth.py — re-derive this test"

    tool = _tool_source()
    missing = sorted(k for k in identity if f'"{k}"' not in tool)
    assert not missing, (
        f"the harness never sets {missing}, which a real login does. That is how "
        "`account` reported 'Session expirée' as a product defect on the first run."
    )


def test_a_download_only_page_is_not_called_a_dead_end():
    """`AppTest` has no `download_button`; the source must be consulted instead."""
    tool = _tool_source()
    assert "_offers_a_download" in tool, (
        "the download check is gone — `process_guide`, whose only actions are two "
        "downloads, will be reported as a dead end again."
    )
    assert "download_button" in tool and "link_button" in tool, (
        "_offers_a_download no longer looks for both shapes of 'hands the artist a "
        "file or a link out'."
    )


def test_the_throwaway_tenant_looks_like_a_real_signup():
    """Both rows, or every page that reads the user invents a finding."""
    tool = _tool_source()
    assert "INSERT INTO saas_users" in tool, (
        "the throwaway tenant no longer creates a saas_users row. A real signup "
        "creates one; without it `account` answers 'Utilisateur introuvable' and the "
        "tool reports that as a product defect."
    )
    assert "DELETE FROM saas_users" in tool, (
        "the throwaway user is never deleted — this tool must leave no trace."
    )


def test_reading_an_existing_artist_never_writes():
    """With --artist the tool looks through real eyes; it must not touch the data."""
    tree = ast.parse(_tool_source())
    fn = next((f for f in ast.walk(tree)
               if isinstance(f, ast.FunctionDef) and f.name == "main"), None)
    assert fn is not None
    body = ast.get_source_segment(_tool_source(), fn) or ""
    # The only writes in main() must be inside the throwaway branch.
    assert "_drop_throwaway" in body and "if throwaway:" in body, (
        "main() no longer gates cleanup on the throwaway branch — with --artist it "
        "could delete a real tenant."
    )
