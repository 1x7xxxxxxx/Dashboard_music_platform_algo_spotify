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
    """Lines returning or printing a whole caught exception, or an ALIAS of one.

    Following the alias is not a refinement — it is the half that was missing.
    Measured in production 2026-08-23: `src/utils/retry.py` was inside this guard's
    scope and green, because it does

        except Exception as exc:
            last_exc = exc          # <- the exception escapes the handler by name
        ...
        logger.error(f"... Dernière erreur : {last_exc}")   # <- rendered OUTSIDE it

    The old walk only looked *inside* `ast.ExceptHandler`, so the YouTube API key was
    written in clear into the Airflow task log every night while this test passed.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # Seed with every `except ... as NAME`, then follow plain `alias = NAME`
    # rebindings to a fixpoint — an exception does not stop being one when it is
    # copied to another variable.
    tainted = {h.name for h in ast.walk(tree)
               if isinstance(h, ast.ExceptHandler) and h.name}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
                continue
            if node.value.id not in tainted:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in tainted:
                    tainted.add(target.id)
                    changed = True

    out = []
    for node in ast.walk(tree):
        # str(e) — the whole message, credentials included
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "str":
            if node.args and getattr(node.args[0], "id", None) in tainted:
                out.append(node.lineno)
        # f"{e}" — same thing. `f"{safe_error(e)}"` wraps a Call, not a Name, so a
        # redacted render is correctly NOT flagged.
        if isinstance(node, ast.FormattedValue):
            if getattr(node.value, "id", None) in tainted:
                out.append(node.lineno)
    return sorted(set(out))


# DERIVED, not hand-listed, and TRANSITIVE.
#
# Two widenings, each paid for by a defect that survived the previous scope:
#
# 1. The first version named five files by hand — the four connection probes and
#    central_apps. A full-application audit then found the same defect in every
#    COLLECTOR, which was in none of them. A guard whose scope is a literal list
#    protects exactly the sites someone remembered.
# 2. The second version asked "does this module call an HTTP client?". That is the
#    wrong question, and `airflow/dags/youtube_daily.py` proved it in production on
#    2026-08-23: a DAG calls no HTTP client at all — it CATCHES AND LOGS the exception
#    the collector raised, and that exception carries the prepared URL. Same shape as
#    `src/utils/retry.py`, which only qualified by the accident of importing requests
#    for its retriable-exception tuple.
#
# The question that actually matches the risk is "can an exception born at an HTTP
# call reach this module?", so the scope is the transitive closure of the import
# graph: a module is in scope if it calls an HTTP client, or imports one that is.
_HTTP_MARKERS = ("requests.", "googleapiclient", "urlopen")
_SCOPE_DIRS = ("src/collectors", "src/utils", "src/dashboard/views/credentials",
               "airflow/dags")


def _module_name(path: Path) -> str:
    return path.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")


def _modules_that_call_http() -> list[str]:
    sources: dict[str, tuple[str, Path]] = {}
    for sub in _SCOPE_DIRS:
        for path in sorted((ROOT / sub).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            sources[_module_name(path)] = (path.read_text(encoding="utf-8"), path)

    # Seed: modules that touch an HTTP client themselves.
    tainted = {mod for mod, (text, _) in sources.items()
               if any(m in text for m in _HTTP_MARKERS)}

    # Closure: a module that imports a tainted module handles its exceptions.
    changed = True
    while changed:
        changed = False
        for mod, (text, path) in sources.items():
            if mod in tainted:
                continue
            tree = ast.parse(text)
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(a.name for a in node.names)
            if any(i in tainted for i in imported):
                tainted.add(mod)
                changed = True

    return [sources[m][1].relative_to(ROOT).as_posix()
            for m in sorted(tainted)
            if "except" in sources[m][0]]


@pytest.mark.parametrize("rel", _modules_that_call_http())
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
