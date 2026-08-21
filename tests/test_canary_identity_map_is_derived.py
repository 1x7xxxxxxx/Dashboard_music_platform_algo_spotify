"""Guard — the canary tool derives its identity map, and holds none of its own.

Split out of `tests/test_create_canary.py` because that file is DB-gated as a whole
and these three assertions need no database. They were invisible on any developer
machine without Postgres on 5433 — which is where the omission they now catch was
introduced in the first place.

The assertion these replace read `tool._IDENTITY_FIELD == _core.UNIQUE_IDENTITY_FIELDS`
and was GREEN while both sides were wrong: four entries each, `instagram` missing
from both. Two copies agreeing says nothing about either being right, and here the
agreement HELD the gap in place — adding Instagram to one side would have failed it.

Error class: `guard-derived-from-the-thing-it-guards`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "create_canary.py"


def _canary_module():
    sys.path.insert(0, str(REPO))
    import importlib.util

    spec = importlib.util.spec_from_file_location("create_canary", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_identity_map_derives_from_the_registry():
    """Both sides must derive from ONE registry — equality between copies is not a guard.

    This assertion used to read `tool._IDENTITY_FIELD == _core.UNIQUE_IDENTITY_FIELDS`
    and it was GREEN while both were wrong: both had four entries, both omitted
    `instagram`. Two copies agreeing says nothing about either being right, and here
    the agreement actively HELD the gap in place — any attempt to add Instagram to
    one side would have failed this test.
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    mod = _canary_module()
    expected = {k: v.field for k, v in PLATFORM_IDENTITIES.items()}
    assert dict(mod._IDENTITY_FIELD) == expected, (
        "tools/create_canary.py no longer derives from tenant_identity:\n"
        f"  tool     {sorted(mod._IDENTITY_FIELD.items())}\n"
        f"  registry {sorted(expected.items())}"
    )


def test_the_tool_holds_no_identity_map_of_its_own():
    """The assertion the equality check could never make.

    A literal pasted back into the tool would still satisfy an equality test the day
    it happens to match. It must not be possible to HAVE a second copy at all.
    """
    import ast

    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    known_fields = {"user_id", "channel_id", "account_id", "spotify_artist_id", "ig_user_id"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        values = [v.value for v in node.values
                  if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        if values and set(values) <= known_fields and len(values) >= 3:
            raise AssertionError(
                f"tools/create_canary.py holds its own platform→field map at line "
                f"{node.lineno} ({values}) — derive it from tenant_identity instead"
            )


def test_the_canary_can_exercise_every_platform_an_artist_can_connect():
    """The reason the omission mattered: the watchdog was blind to Instagram.

    A canary that cannot declare a platform cannot prove that platform works for a
    tenant — and Instagram is the platform that broke in the most recent artist test.
    """
    from src.dashboard.views.credentials._registry import CONNECTION_TESTS

    mod = _canary_module()
    missing = set(CONNECTION_TESTS) - set(mod._IDENTITY_FIELD)
    assert not missing, (
        f"an artist can connect {sorted(missing)} but the canary cannot declare it — "
        f"the tenant whose job is catching credential failures is blind to it"
    )
