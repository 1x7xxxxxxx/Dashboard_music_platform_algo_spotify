"""Tests for the onboarding focus picker — content model + carried selection.

The beta tester (Grinch, 2026-08-12) faced six platforms listed flat, with no
statement of what any of them buys, and stopped. These tests pin the two things
that make the list answerable: every platform states a decision it unlocks and
an honest cost, and a "recommended" set small enough to actually recommend.
"""
import pytest

from src.dashboard.content.platform_value import (
    BY_KEY,
    CREDENTIALS,
    CSV,
    PLATFORM_VALUES,
    RECOMMENDED,
    ordered_for_setup,
    total_effort,
)
from src.dashboard.utils.setup_focus import progress, remaining


# ── The content contract ─────────────────────────────────────────────────────

@pytest.mark.parametrize("pv", PLATFORM_VALUES, ids=lambda p: p.key)
def test_every_platform_states_value_need_and_cost(pv):
    assert pv.value and len(pv.value) > 30, "value must name a decision, not a feature"
    assert pv.need, "the artist must know what to go and find"
    assert 0 < pv.effort_min <= 15, "an honest first-time estimate"
    assert pv.where in (CREDENTIALS, CSV)


def test_recommended_set_is_small_enough_to_be_a_recommendation():
    assert 1 <= len(RECOMMENDED) <= 2, (
        "recommending half the list recommends nothing"
    )


def test_recommended_pair_is_spotify_and_instagram():
    """The pair chosen with the user: where streams come from + whether people follow."""
    assert set(RECOMMENDED) == {"spotify", "instagram"}


def test_recommended_start_is_under_ten_minutes():
    assert total_effort(RECOMMENDED) <= 10


def test_platforms_that_fail_for_real_people_carry_a_caveat():
    """Each caveat here is a failure actually observed in a beta session."""
    for key in ("instagram", "soundcloud", "youtube", "meta"):
        assert BY_KEY[key].caveat, f"{key} has a known silent-failure mode; say it"


# ── Ordering ────────────────────────────────────────────────────────────────

def test_order_puts_recommended_first_then_cheapest():
    keys = [p.key for p in ordered_for_setup(set())]
    assert keys[:2] == list(RECOMMENDED) or set(keys[:2]) == set(RECOMMENDED)
    rest = [BY_KEY[k].effort_min for k in keys[2:]]
    assert rest == sorted(rest), "after the recommended pair, cheapest first"


def test_connected_platforms_sink_to_the_bottom():
    keys = [p.key for p in ordered_for_setup({"spotify"})]
    # Already connected → last, despite being a recommended platform.
    assert keys[-1] == "spotify"
    assert keys[0] == "instagram", "the remaining recommended one leads"


# ── The carried selection ───────────────────────────────────────────────────

def test_progress_counts_the_artists_own_selection_not_all_platforms():
    """2/2 must not read as 2/6 — progress against a plan they never made."""
    assert progress(["spotify", "instagram"], {"spotify"}) == (1, 2)
    assert progress(["spotify", "instagram"], {"spotify", "instagram"}) == (2, 2)


def test_remaining_preserves_the_chosen_order():
    assert remaining(["instagram", "spotify", "youtube"], {"spotify"}) == \
        ["instagram", "youtube"]


def test_empty_focus_is_harmless():
    assert progress(None, {"spotify"}) == (0, 0)
    assert remaining(None, set()) == []


def test_total_effort_ignores_unknown_keys():
    assert total_effort(["spotify", "not_a_platform"]) == BY_KEY["spotify"].effort_min


# ── Instagram has no row of its own ─────────────────────────────────────────

def test_instagram_counts_as_connected_from_the_meta_row():
    """Otherwise the ⭐-recommended platform can never be ticked off."""
    from src.dashboard.utils.setup_focus import connected_platforms

    rows = {"meta": {"extra_config": {"account_id": "act_1", "ig_user_id": "178414"}}}
    assert connected_platforms(rows) == {"meta", "instagram"}


def test_meta_without_instagram_stays_meta_only():
    from src.dashboard.utils.setup_focus import connected_platforms

    assert connected_platforms({"meta": {"extra_config": {"account_id": "act_1"}}}) == {"meta"}


def test_connected_platforms_survives_jsonb_as_text_and_nulls():
    """A row is not a connection.

    These three cases used to expect `{"meta"}` — the row exists, so Meta counted as
    connected — even when it carried NO ad account, or an `extra_config` that could
    not be parsed at all. That is `row-existence-read-as-connection`: the KPI strip
    said ✅ while the readiness matrix said ⚪, on the same data.

    A meta row holding only `ig_user_id` connects INSTAGRAM, not Meta. They are two
    identities that happen to share a row.
    """
    from src.dashboard.utils.setup_focus import connected_platforms

    assert connected_platforms({"meta": {"extra_config": '{"ig_user_id": "1"}'}}) == \
        {"instagram"}
    assert connected_platforms({"meta": {"extra_config": None}}) == set()
    assert connected_platforms({"meta": {"extra_config": "not json"}}) == set()
    assert connected_platforms({"meta": {"extra_config": {"account_id": "   "}}}) == set()
    assert connected_platforms({}) == set()
    assert connected_platforms(None) == set()
