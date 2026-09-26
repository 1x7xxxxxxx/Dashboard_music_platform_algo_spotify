"""Ratchet — the identity registry may not silently shrink.

Error class `guard-derived-from-the-thing-it-guards`.

`tests/test_identity_uniqueness.py` parametrises its cases over the registry:

    @pytest.mark.parametrize("platform,field", sorted(UNIQUE_IDENTITY_FIELDS.items()))

A parametrised suite cannot fail for a MISSING entry. Removing one removes its test
cases; the run goes from "N passed" to "N-3 passed", both green. That is how
`instagram` stayed out of the uniqueness map long enough for two tenants to be able
to claim the same Instagram Business Account in silence — and why nobody noticed:
the guard derived its own scope from the thing it was guarding.

A literal list is the only assertion a parametrised suite cannot make about itself.
Shrinking it must be a deliberate edit to THIS file, with a reason.

Not DB-gated on purpose: the omission was introduced on a machine where every
DB-gated test skipped.
"""
from __future__ import annotations

from src.utils.tenant_identity import PLATFORM_IDENTITIES

# Every logical platform a tenant can declare an identity for. Adding one is a
# feature; removing one is a decision that must be argued here, not a side effect.
_EXPECTED = frozenset({"soundcloud", "spotify", "youtube", "meta", "instagram"})


def test_the_registry_lists_exactly_these_platforms() -> None:
    actual = frozenset(PLATFORM_IDENTITIES)
    assert actual == _EXPECTED, (
        f"the identity registry changed shape.\n"
        f"  missing: {sorted(_EXPECTED - actual)}\n"
        f"  added:   {sorted(actual - _EXPECTED)}\n"
        f"Adding is fine — extend _EXPECTED. Removing means a platform loses its "
        f"uniqueness rule, its canary coverage and its connection test at once."
    )


def test_instagram_is_a_first_class_identity_not_a_meta_field() -> None:
    """The specific entry whose absence cost a beta session, pinned by name."""
    spec = PLATFORM_IDENTITIES["instagram"]
    assert spec.field == "ig_user_id"
    assert spec.storage == "meta", (
        "Instagram's identity must be stored in the meta row — a platform='instagram' "
        "row is an orphan the collectors never read"
    )
    assert spec.logical == "instagram"


def test_uniqueness_map_covers_the_whole_registry() -> None:
    from src.dashboard.views.credentials._core import UNIQUE_IDENTITY_FIELDS

    assert set(UNIQUE_IDENTITY_FIELDS) == set(PLATFORM_IDENTITIES), (
        "the uniqueness map and the registry disagree — the map is what "
        "find_identity_conflict consults, so a platform absent from it can be "
        "claimed by two tenants with no refusal"
    )


def expectation_is_literal(source: str, name: str = "_EXPECTED") -> bool:
    """Is `name` bound to a literal set of strings — not DERIVED from anything? Pure.

    The class this file guards is precisely an expectation computed from the thing under
    test. `_EXPECTED = frozenset(PLATFORM_IDENTITIES)` would keep every test here green
    while `instagram` vanished from both sides at once.
    """
    import ast

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            value = node.value
            if isinstance(value, ast.Call) and not value.keywords and len(value.args) == 1:
                value = value.args[0]
            return isinstance(value, (ast.Set, ast.List, ast.Tuple)) and all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in value.elts)
    return False


def test_the_expectation_is_written_not_derived() -> None:
    from pathlib import Path

    assert expectation_is_literal(Path(__file__).read_text(encoding="utf-8")), (
        "_EXPECTED is no longer a literal list of platform names — an expectation "
        "derived from the registry cannot fail when the registry loses an entry.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity, both halves: the derived form is refused, the literal one accepted."""
    assert not expectation_is_literal("_EXPECTED = frozenset(PLATFORM_IDENTITIES)\n")
    assert not expectation_is_literal("_EXPECTED = set(UNIQUE_IDENTITY_FIELDS)\n")
    assert not expectation_is_literal("_EXPECTED = frozenset({SPEC.name, 'meta'})\n")
    assert expectation_is_literal("_EXPECTED = frozenset({'soundcloud', 'meta'})\n")
