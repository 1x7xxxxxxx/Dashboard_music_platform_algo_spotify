"""
Guard — an action that belongs to a tenant may not proceed with an unknown tenant.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/views/**
Persists in: nothing

Error classes: `unattributable-payment-link`, `artist-id-or-1`.

Two shapes, one question: *can this run when we do not know whose it is?*

1. A Stripe Payment Link without `client_reference_id`. The webhook
   (`stripe_webhook.py:140`) executes `if artist_id and customer_id:` — with no
   `client_reference_id` it does NOTHING. The customer's card is charged and no plan is
   ever provisioned. Measured 2026-08-23 (R40): BOTH payment surfaces degraded silently,
   `f"{url}?client_reference_id={_aid}" if _aid else checkout_url`, so a session that had
   lost its artist id still rendered a payable button. An unattributable payment link is
   worse than no link.

2. `get_artist_id() or 1` — CLAUDE.md rule #7. A tenant whose identity failed to resolve
   is served the ADMIN's data. This is the exact shape of the `track_popularity_history`
   leak, and its error class sat catalogued as `artist-id-or-1` / P1 / **open, no guard**
   until this file. Golding puts the reason plainly (*Building Multi-Tenant SaaS
   Architectures*, p.204): filtering a query by tenant is not the same as being unable to
   read another tenant.

Both are read from the AST, never from text: the previous four guards written in this
repo failed on their own explanatory comments.
"""

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"
_TENANT_CALLS = {"get_artist_id", "tenant_scope"}


def _view_files() -> list[str]:
    return sorted(str(p.relative_to(_ROOT)) for p in _VIEWS.rglob("*.py"))


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _name_of(node.func)
    return getattr(node, "id", getattr(node, "attr", ""))


def _assignments(tree: ast.Module) -> dict[str, ast.AST]:
    """`name -> assigned expression`, for the one-level resolution below."""
    out: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name):
                out.setdefault(tgt.id, node.value)
    return out


def _url_leaves(node: ast.AST, env: dict[str, ast.AST], depth: int = 0) -> list[ast.AST]:
    """Every expression the URL argument can actually evaluate to.

    Resolves plain `Name` arguments through `env`. Without that step this guard was
    GREEN on the very defect it was written for: the offending code passed the variable
    `_url`, assigned one line above from
    `f"…client_reference_id={_aid}" if _aid else checkout_url`. Looking only at the call
    site, the guard saw a bare Name, decided it was not a checkout link, and skipped it.
    Caught by mutating the fix away — never by reading the guard.
    """
    if depth > 4:
        return [node]
    if isinstance(node, ast.IfExp):
        return (_url_leaves(node.body, env, depth + 1)
                + _url_leaves(node.orelse, env, depth + 1))
    if isinstance(node, ast.BoolOp):
        return [leaf for v in node.values for leaf in _url_leaves(v, env, depth + 1)]
    if isinstance(node, ast.Name) and node.id in env:
        return _url_leaves(env[node.id], env, depth + 1)
    return [node]


def _mentions(node: ast.AST, needle: str) -> bool:
    return any(
        (isinstance(n, ast.Constant) and isinstance(n.value, str) and needle in n.value)
        or getattr(n, "id", None) == needle
        or getattr(n, "attr", None) == needle
        for n in ast.walk(node)
    )


def test_the_scope_is_not_empty() -> None:
    assert len(_view_files()) > 30, "the views walk found almost nothing"


@pytest.mark.parametrize("rel", _view_files())
def test_no_payment_link_can_render_without_its_tenant(rel: str) -> None:
    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    env = _assignments(tree)
    bad: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _name_of(node.func) == "link_button"):
            continue
        url_arg = node.args[1] if len(node.args) > 1 else next(
            (kw.value for kw in node.keywords if kw.arg == "url"), None)
        if url_arg is None:
            continue
        leaves = _url_leaves(url_arg, env)
        # Only judge links that are Stripe checkout links at all.
        if not any(_mentions(leaf, "checkout_url") for leaf in leaves):
            continue
        if not all(_mentions(leaf, "client_reference_id") for leaf in leaves):
            bad.append(node.lineno)

    assert not bad, (
        f"{rel} line(s) {bad}: a Stripe checkout link can render WITHOUT "
        f"`client_reference_id`. The webhook runs `if artist_id and customer_id:` — "
        f"without it the payment succeeds and no plan is ever provisioned. Render a "
        f"disabled button and say why, instead of a payable link nobody can attribute."
    )


@pytest.mark.parametrize("rel", _view_files())
def test_a_missing_tenant_never_falls_back_to_a_hardcoded_one(rel: str) -> None:
    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    bad: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        first, *rest = node.values
        if _name_of(first) not in _TENANT_CALLS:
            continue
        for alt in rest:
            if isinstance(alt, ast.Constant):
                bad.append((node.lineno, f"{_name_of(first)}() or {alt.value!r}"))

    assert not bad, (
        f"{rel}: {bad} — CLAUDE.md rule #7. A tenant whose identity failed to resolve "
        f"must never be served another tenant's rows; a hardcoded fallback serves the "
        f"ADMIN's. Stop the session (`st.error(...); st.stop()`) or use `view_session()`."
    )
