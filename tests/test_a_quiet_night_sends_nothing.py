"""
Guard — a night with no real finding produces no email.

Type: Sub
Uses: src.utils.monitoring_checks.tenant_freshness_gaps
Triggers: pytest
Depends on: src/utils/monitoring_checks.py, src/utils/freshness_monitor.py
Persists in: nothing

Error class: watchdog-becomes-the-noise.

Measured in production 2026-08-23 by reading the xcom sizes of the last nightly run:
`check_data_freshness` 1083 bytes, `check_credentials_all` 810, `check_onboarding_readiness`
918 — all three non-empty on EVERY pass. `has_issues` was therefore true every night,
the "quiet night" branch was unreachable, and the digest was on its way to becoming the
daily noise it exists to avoid. A red that arrives every night stops being read; a green
is never questioned.

The suppressions must be MEASURED, never a list of names — that is the contract
`expected_silence` established (`freshness_monitor._silence_reason`: an unknown rule, a
failed query or an ACTIVE campaign all KEEP the alert). These tests pin that a doubt
keeps the alert, which is the half that makes suppression safe.
"""

from src.utils.monitoring_checks import tenant_freshness_gaps


def _r(source: str, stale: bool, **kw) -> dict:
    return {"source": source, "stale": stale, "stale_h": 48, **kw}


def test_a_platform_proven_by_another_source_is_not_a_gap() -> None:
    """Spotify is proven by the API table OR the S4A CSV — best-of, like readiness.

    This single line was most of the permanent noise: every API-only tenant was
    reported stale on "Spotify S4A" nightly while their Spotify was perfectly fresh.
    """
    gaps = tenant_freshness_gaps(
        [(12, "Benken", [_r("Spotify API", False), _r("Spotify S4A", True)])],
        {12: {"spotify"}},
    )
    assert gaps == [], f"a fresh Spotify was reported as a gap: {gaps}"


def test_a_platform_stale_on_every_source_is_still_a_gap() -> None:
    gaps = tenant_freshness_gaps(
        [(12, "Benken", [_r("Spotify API", True), _r("Spotify S4A", True)])],
        {12: {"spotify"}},
    )
    assert len(gaps) == 1 and gaps[0]["artist_id"] == 12
    assert set(gaps[0]["stale_sources"]) == {"Spotify API", "Spotify S4A"}


def test_a_platform_the_tenant_never_declared_is_not_a_gap() -> None:
    """It is a platform they do not use, not a failure."""
    gaps = tenant_freshness_gaps(
        [(13, "GRiNCH", [_r("YouTube", True), _r("SoundCloud", True)])],
        {13: {"soundcloud"}},
    )
    assert len(gaps) == 1
    assert gaps[0]["stale_sources"] == ["SoundCloud"], (
        f"YouTube was reported for a tenant who never declared it: {gaps}"
    )


def test_a_source_no_platform_claims_is_never_a_tenant_gap() -> None:
    """"Apple Music" is monitored globally but claimed by no platform registry entry.

    Asserted with NO declaration map on purpose. With one, the "not declared by this
    tenant" filter would also suppress it, and this assertion would pass for the wrong
    reason — a mutation removing the unattributable-source guard stayed green until the
    map was taken out of the fixture.
    """
    gaps = tenant_freshness_gaps([(12, "Benken", [_r("Apple Music", True)])])
    assert gaps == [], f"an unattributable source became a tenant gap: {gaps}"


def test_a_doubt_keeps_the_alert() -> None:
    """No declaration map, or no entry for this tenant, suppresses NOTHING.

    This is the property that makes the whole suppression safe. `_silence_reason` has
    the same shape: an unknown rule, a failed query and an active campaign all return
    None so the alert survives.
    """
    rows = [_r("YouTube", True)]
    assert tenant_freshness_gaps([(12, "Benken", rows)]) != [], "no map ⇒ no suppression"
    assert tenant_freshness_gaps([(12, "Benken", rows)], {}) != [], "empty map ⇒ none"
    assert tenant_freshness_gaps([(12, "Benken", rows)], {99: {"youtube"}}) != [], (
        "an entry for ANOTHER tenant must not suppress this one"
    )


def test_a_healthy_fleet_produces_no_gap_at_all() -> None:
    """The end-to-end shape of a quiet night."""
    fleet = [
        (1, "admin", [_r("Spotify API", False), _r("YouTube", False),
                      _r("SoundCloud", False), _r("Apple Music", True)]),
        (12, "Benken", [_r("SoundCloud", False), _r("Spotify S4A", True)]),
    ]
    declared = {1: {"spotify", "youtube", "soundcloud"}, 12: {"soundcloud"}}
    assert tenant_freshness_gaps(fleet, declared) == []


def test_a_broken_fleet_still_names_the_tenant() -> None:
    fleet = [(12, "Benken", [_r("YouTube", True)])]
    gaps = tenant_freshness_gaps(fleet, {12: {"youtube", "soundcloud"}})
    assert len(gaps) == 1
    assert gaps[0]["artist_name"] == "Benken", "the tenant must be named, not counted"
