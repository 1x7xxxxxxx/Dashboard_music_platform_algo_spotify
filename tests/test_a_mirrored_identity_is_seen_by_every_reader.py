"""The nightly mail announced a missing credential that is present.

Measured on PRODUCTION data, 2026-08-26:

    saas_artists      id=1 '1x7xxxxxxx'  spotify_artist_id = 7sbfafbLjNZGZJZjZ3xoPB
    artist_credentials  id=1 → meta, soundcloud, youtube.   NO spotify row at all.

`PLATFORM_IDENTITIES['spotify']` declares `mirror='spotify_artist_id'`, and
`artist_readiness._identity` honours it explicitly. `declared_identities` did not —
it read `extra_config` and nothing else. So the two readers of one question answered
differently, and the one that runs unattended was the wrong one: "🔑 Credentials
manquants — 1x7xxxxxxx / spotify", every night, for an identity that is set.

It matters more than one stray row. After the duplicate-subtraction of the same day,
that line is the ONLY one left in its section — so the mail would have concentrated
itself onto a false positive, which is the worst possible outcome of a de-noising.

The guard is on the AGREEMENT, not on Spotify: any platform whose spec carries a
`mirror` must be visible to both readers, so a second mirrored identity added later
cannot reintroduce the split.
"""
from __future__ import annotations

import pytest

from src.utils.tenant_identity import (
    IDENTITY_MIRRORS, PLATFORM_IDENTITIES, declared_identities,
)


def test_the_registry_still_declares_at_least_one_mirror():
    """Non-vacuity: every assertion below iterates the mirrors."""
    assert IDENTITY_MIRRORS, "no mirrored identity left — this guard asserts nothing"
    assert IDENTITY_MIRRORS.get("spotify") == "spotify_artist_id"


@pytest.mark.parametrize("logical", sorted(IDENTITY_MIRRORS))
def test_a_mirror_only_identity_counts_as_declared(logical):
    """The production shape of tenant 1: nothing in extra_config, value on the mirror."""
    assert logical not in declared_identities({}), "fixture is not reproducing the gap"
    assert logical in declared_identities({}, {logical: "7sbfafbLjNZGZJZjZ3xoPB"}), (
        f"{logical} is declared on its mirror and this reader cannot see it — the "
        "nightly mail reports a missing credential that is present")


@pytest.mark.parametrize("logical", sorted(IDENTITY_MIRRORS))
def test_an_empty_mirror_is_not_a_declaration(logical):
    """An absent identity and an empty one are the same thing at the call site."""
    for empty in (None, "", "   "):
        assert logical not in declared_identities({}, {logical: empty})


def test_extra_config_still_wins_when_both_are_set():
    """The mirror is a fallback, never an override: the row is what the artist typed."""
    spec = PLATFORM_IDENTITIES["spotify"]
    got = declared_identities({spec.storage: {spec.field: "A" * 22}},
                              {"spotify": "B" * 22})
    assert "spotify" in got


def test_a_non_mirrored_platform_ignores_a_stray_mirror_value():
    """Passing a value for a platform that declares no mirror must change nothing —
    otherwise the fallback becomes a way to fake any identity."""
    assert "youtube" not in declared_identities({}, {"youtube": "UC" + "x" * 22})


def test_both_readers_agree_on_the_production_row():
    """`artist_readiness._identity` and `declared_identities` on tenant 1's shape.

    The two functions are the ones that disagreed; asserting them side by side is the
    only assertion that would have failed before the fix.
    """
    from src.utils.artist_readiness import _identity

    creds, mirror = {}, "7sbfafbLjNZGZJZjZ3xoPB"
    readiness_says = _identity("spotify", creds, mirror)
    credentials_says = "spotify" in declared_identities(creds, {"spotify": mirror})
    assert readiness_says == credentials_says is True, (
        f"readiness={readiness_says} credentials={credentials_says} — one reader sees "
        "the mirrored identity and the other does not")


def test_the_alert_monitor_passes_the_mirrors_in():
    """A mirror-aware function nobody hands mirrors to is still the old behaviour."""
    import pathlib
    dag = (pathlib.Path(__file__).resolve().parents[1]
           / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8")
    assert "declared_identities(extra_by_platform, _mirrored_identities(artist_id))" in dag, (
        "check_credentials_all reads identities without the mirrors again")
    assert "from src.utils.tenant_identity import IDENTITY_MIRRORS" in dag, (
        "the mirror column is hand-written instead of read from the registry")
