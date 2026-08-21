"""Guard — the security defects a pentest of this session's changes found.

Error class `tenant-identity-reaches-a-url-unvalidated` (new) plus
`secret-in-an-exception-message` (new).

Three real findings, all reachable by a normal tenant:

1. **Path injection with the platform's own token.** `ig_user_id` is free text and
   is interpolated into a Graph API path. `requests` does not percent-encode `/`
   in a path you build yourself — verified: `me/accounts` produces
   `https://graph.facebook.com/v24.0/me/accounts?access_token=<SYSTEM_USER_TOKEN>`.
   The probe then echoed `ri.text[:150]` back to the tenant on a 200-with-no-username,
   and `/me/accounts` returns Page access tokens minted from that System User token.

2. **Uniqueness present, derived, tested, unreachable.** `_handle_save` called
   `find_identity_conflict` with the TAB key, so the meta tab only ever compared
   `account_id`; `ig_user_id` was never checked against another tenant. The test
   passed because it called with the LOGICAL name — a call the save path never made.

3. **Secrets in exception messages.** Meta and YouTube pass their credential as a
   QUERY PARAMETER, so a `requests` exception message embeds the whole prepared URL.
   `str(e)` was returned to the tenant (st.error) and printed nightly into the
   Airflow task log by `central_apps.check_meta`. A DNS blip was enough.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.utils.tenant_identity import (
    PLATFORM_IDENTITIES,
    identity_is_well_formed,
    malformed_identities,
)

ROOT = Path(__file__).resolve().parent.parent
CRED = ROOT / "src/dashboard/views/credentials"


# ── 1. shape ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    "me/accounts", "me/adaccounts", "123/me", "1/../me", "me%2Faccounts",
    "17841400000000000?fields=x", "17841400000000000/media",
])
def test_a_path_payload_is_never_a_well_formed_identity(payload: str) -> None:
    for logical in PLATFORM_IDENTITIES:
        assert not identity_is_well_formed(logical, payload), (
            f"{logical} accepts {payload!r} — this value reaches a REST path"
        )


def test_real_identifiers_are_still_accepted() -> None:
    assert identity_is_well_formed("instagram", "17841400000000000")
    assert identity_is_well_formed("meta", "567214713853881")
    assert identity_is_well_formed("meta", "act_567214713853881")
    assert identity_is_well_formed("spotify", "7sbfafbLjNZGZJZjZ3xoPB")
    assert identity_is_well_formed("youtube", "UCDpjL6K1yoGdCm4M3PEdskg")
    assert identity_is_well_formed("soundcloud", "377065610")


def test_the_shape_check_is_a_fullmatch() -> None:
    """`re.match` would accept `123/me/accounts`, which is the entire attack."""
    assert not identity_is_well_formed("instagram", "123/me/accounts")
    assert not identity_is_well_formed("instagram", "17841400000000000junk")


def test_malformed_identities_reports_the_offender() -> None:
    bad = malformed_identities({"meta": {"ig_user_id": "me/accounts",
                                         "account_id": "567214713853881"}})
    assert bad == {"instagram": "me/accounts"}


def test_the_instagram_probe_refuses_before_the_network() -> None:
    from src.dashboard.views.credentials._platform_meta import _test_instagram

    ok, msg = _test_instagram({"ig_user_id": "me/accounts", "access_token": "tok"})  # pragma: allowlist secret
    assert ok is False
    assert "invalide" in msg.lower() or "chiffres" in msg.lower(), msg


# ── 2. uniqueness reaches every identity of a tab ─────────────────────────────

def test_the_save_path_checks_every_identity_the_tab_carries() -> None:
    """AST: `find_identity_conflict` must be called inside a loop over the registry.

    Called once with `platform_key`, the meta tab compares `account_id` only —
    which is what shipped, guarded and green, while `ig_user_id` was free to be
    claimed twice.
    """
    tree = ast.parse((CRED / "_render.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "find_identity_conflict"]
    assert calls, "find_identity_conflict is no longer called at save time"
    for call in calls:
        third = call.args[2] if len(call.args) > 2 else None
        assert not (isinstance(third, ast.Name) and third.id == "platform_key"), (
            "find_identity_conflict is called with the TAB key — the meta tab then "
            "only ever compares account_id, and ig_user_id can be claimed twice"
        )


# ── 3. no credential may reach a message ─────────────────────────────────────

def _returns_bare_exception(path: Path) -> list[int]:
    """Lines returning or printing a whole caught exception."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or not handler.name:
            continue
        name = handler.name
        for node in ast.walk(handler):
            # str(e) / f"{e}" anywhere in the handler body
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "str":
                if node.args and getattr(node.args[0], "id", None) == name:
                    out.append(node.lineno)
            if isinstance(node, ast.FormattedValue):
                if getattr(node.value, "id", None) == name:
                    out.append(node.lineno)
    return sorted(set(out))


@pytest.mark.parametrize("rel", [
    "src/dashboard/views/credentials/_platform_meta.py",
    "src/dashboard/views/credentials/_platform_youtube.py",
    "src/dashboard/views/credentials/_platform_spotify.py",
    "src/dashboard/views/credentials/_platform_soundcloud.py",
    "src/utils/central_apps.py",
])
def test_no_probe_surfaces_a_whole_exception(rel: str) -> None:
    """These modules pass credentials as query parameters.

    A `requests` exception message embeds the full prepared URL, so rendering the
    exception renders the credential — to the tenant (st.error) or into the nightly
    Airflow log. `type(e).__name__` says as much as the reader needs.
    """
    lines = _returns_bare_exception(ROOT / rel)
    assert not lines, (
        f"{rel} surfaces a caught exception verbatim at line(s) {lines}. These "
        f"modules put credentials in the query string — the message contains them."
    )


def test_the_raw_response_body_is_never_echoed() -> None:
    src = (CRED / "_platform_meta.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
            if node.value.attr == "text":
                raise AssertionError(
                    f"line {node.lineno}: a raw Graph response body is sliced and "
                    f"surfaced — on a 200 with no expected field this returned "
                    f"whatever the tenant-chosen path produced, including tokens"
                )
