"""The new-tenant render pass must render as a TENANT — never as the admin, never as artist 1.

Type: Test
Uses: ast, tests/render_harness.py (SCRIPT, TENANT_SCRIPT, EMPTY_TENANT_VIEWS)
Depends on: nothing (reads the render scripts, renders nothing — runs without a database)
Persists in: nothing

Error class `multitenant-mono-test-blindspot`. Audit of 2026-06-19: every render smoke
test ran with `role="admin"` and `artist_id=1`. Artist 1 is the admin — years of data,
every identity declared, and (as admin) no SQL tenant filter at all: the single
configuration in which a tenant defect CANNOT appear. The rule was written and never
built, and a second beta session failed the same way on 2026-08-20.

`test_views_render_smoke.py::test_view_renders_for_a_brand_new_artist` closes it by
rendering `EMPTY_TENANT_VIEWS` through `TENANT_SCRIPT` for a freshly inserted tenant.
That test is gated on a live database and asserts only « no exception », so nothing
there would notice the script drifting back to the admin session. This file reads the
script's session seed and refuses the two shapes that make the pass blind.

Does NOT cover: whether a render shows ANOTHER tenant's data (`test_e2e_two_tenants.py`
asks that); views outside `EMPTY_TENANT_VIEWS`; the DAGs and exports.
"""
from __future__ import annotations

import ast

from tests.render_harness import EMPTY_TENANT_VIEWS, SCRIPT, TENANT_SCRIPT

_ADMIN_TENANT = 1


def _session_seed(script: str) -> dict[str, object]:
    """`st.session_state["<key>"] = <constant>` assignments of a render script."""
    seed: dict[str, object] = {}
    for node in ast.walk(ast.parse(script)):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        if (isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "session_state"
                and isinstance(target.slice, ast.Constant)
                and isinstance(node.value, ast.Constant)):
            seed[target.slice.value] = node.value.value
    return seed


def why_blind_to_tenants(script: str) -> list[str]:
    """Why a render script cannot expose a tenant defect, or []. Pure."""
    seed = _session_seed(script)
    why = []
    if seed.get("role") != "artist":
        why.append(f"renders as role={seed.get('role')!r}: no tenant filter applies")
    if seed.get("artist_id") == _ADMIN_TENANT:
        why.append("renders tenant 1, the admin — the one tenant a leak cannot show on")
    return why


def _tenant_render(artist_id: int) -> str:
    return TENANT_SCRIPT.format(root="/repo", view=EMPTY_TENANT_VIEWS[0], artist_id=artist_id)


def test_the_new_tenant_pass_renders_as_a_tenant() -> None:
    assert EMPTY_TENANT_VIEWS, "the new-tenant pass renders no view — it proves nothing"
    assert why_blind_to_tenants(_tenant_render(4242)) == [], (
        f"{why_blind_to_tenants(_tenant_render(4242))}: `TENANT_SCRIPT` no longer seeds a "
        "non-admin session for the tenant the fixture created. The render pass is back to "
        "the 2026-06-19 state, where every smoke test ran as artist 1.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The admin pass (`SCRIPT`) and an artist session pinned to tenant 1 are both
    refused; the tenant pass for a fresh tenant is accepted."""
    admin = SCRIPT.format(root="/repo", view="home")
    assert len(why_blind_to_tenants(admin)) == 2, why_blind_to_tenants(admin)

    pinned = _tenant_render(_ADMIN_TENANT)
    assert why_blind_to_tenants(pinned) == [
        "renders tenant 1, the admin — the one tenant a leak cannot show on"]

    assert why_blind_to_tenants(_tenant_render(4242)) == []
