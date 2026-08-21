"""Guard — "connected" means an identity was declared, never that a row exists.

Error class `row-existence-read-as-connection`.

Four surfaces decided connection from the EXISTENCE of an `artist_credentials` row:
the credentials KPI strip, the onboarding checklist, the setup-focus picker and the
home onboarding tracker — the last ticking the whole credentials step on ONE row for
ANY platform. An artist who opened a tab and saved it blank was shown ✅ on all four
while `artist_readiness` showed ⚪ for the same tenant on the same data.

Spotify could manufacture exactly such a row: `_render.py` re-wrote
`extra['spotify_artist_id']` after the empty-value pop, so it was the one platform
able to persist `{"spotify_artist_id": ""}`.

The meta row makes it sharper: it carries TWO identities. A row holding only
`ig_user_id` connects Instagram, not Meta. Counting rows cannot express that.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from src.utils.tenant_identity import declared_identities

ROOT = Path(__file__).resolve().parent.parent


def test_a_blank_identity_is_not_a_connection() -> None:
    assert declared_identities({"spotify": {"spotify_artist_id": ""}}) == set()
    assert declared_identities({"spotify": {"spotify_artist_id": "   "}}) == set()
    assert declared_identities({"youtube": {}}) == set()
    assert declared_identities({}) == set()


def test_a_meta_row_with_only_instagram_connects_instagram_not_meta() -> None:
    assert declared_identities({"meta": {"ig_user_id": "17841400000000000"}}) == {"instagram"}


def test_a_meta_row_with_both_connects_both() -> None:
    got = declared_identities({"meta": {"account_id": "123", "ig_user_id": "456"}})
    assert got == {"meta", "instagram"}


def test_a_declared_identity_is_a_connection() -> None:
    assert declared_identities({"youtube": {"channel_id": "UCabc"}}) == {"youtube"}


# ── The sweep: no surface may go back to counting rows ────────────────────────

_SURFACES = (
    "src/dashboard/views/credentials/_render.py",
    "src/dashboard/views/onboarding.py",
    "src/dashboard/utils/setup_focus.py",
    "src/dashboard/views/home.py",
)


@pytest.mark.parametrize("rel", _SURFACES)
def test_no_surface_counts_credential_rows(rel: str) -> None:
    """`COUNT(*) FROM artist_credentials` with no identity condition is the defect."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    for m in re.finditer(r"COUNT\(\*\)\s*FROM\s+artist_credentials", text, re.I):
        window = text[m.start(): m.start() + 400]
        assert "extra_config" in window, (
            f"{rel}:{text[:m.start()].count(chr(10)) + 1} counts credential rows "
            f"without looking at the identity — a blank save would read as connected"
        )


@pytest.mark.parametrize("rel", ("src/dashboard/utils/setup_focus.py",
                                 "src/dashboard/views/onboarding.py"))
def test_no_surface_builds_connection_from_a_bare_row_set(rel: str) -> None:
    """`set(rows)` / `{r[0] for r in rows}` is the same defect in Python.

    AST, not text: the docstrings of these functions describe the very expression
    being forbidden, because that is how you explain why it is gone.
    """
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    offences = []
    for node in ast.walk(tree):
        # set(rows) / set(rows or {})
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "set" and node.args):
            arg = node.args[0]
            names = {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
            if "rows" in names:
                offences.append(("set(rows)", node.lineno))
        # {r[0] for r in rows}
        if isinstance(node, ast.SetComp):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if "rows" in names:
                offences.append(("{… for … in rows}", node.lineno))
    assert not offences, (
        f"{rel} derives connection from the rows themselves: {offences} — "
        f"use tenant_identity.declared_identities()"
    )


def test_every_surface_actually_calls_the_shared_helper() -> None:
    """If they stop calling it, the cases above keep passing while the UI lies again."""
    missing = [
        rel for rel in _SURFACES
        if "declared_identities" not in (ROOT / rel).read_text(encoding="utf-8")
        and "PLATFORM_IDENTITIES" not in (ROOT / rel).read_text(encoding="utf-8")
    ]
    assert not missing, f"surface(s) no longer consult the identity registry: {missing}"
