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
    """A MINORITY of the list, whatever the list grows to.

    It read `<= 2` until 2026-09-04, which is the same defect one level up: an
    absolute bound pinned to the list's size on the day it was written. Adding
    Spotify for Artists took the registry to seven, and two-of-seven versus
    three-of-seven is not the question — "does the starred group still stand out
    from the rest" is.
    """
    assert RECOMMENDED, "nothing is recommended: the first column would be empty"
    assert len(RECOMMENDED) < len(PLATFORM_VALUES) / 2, (
        f"{len(RECOMMENDED)} of {len(PLATFORM_VALUES)} platforms are recommended — "
        "recommending half the list recommends nothing"
    )


def test_recommended_are_the_three_chosen_with_the_user():
    """Where the streams come from, whether the audience follows, what moves fastest.

    Chosen on 2026-09-04: « à gauche et cochées celles qu'on recommande : spotify
    insta et soundcloud ». All three are a link to paste, and none needs an
    advertising account.
    """
    assert set(RECOMMENDED) == {"spotify", "instagram", "soundcloud"}


def test_recommended_start_is_under_ten_minutes():
    assert total_effort(RECOMMENDED) <= 10


def test_platforms_that_fail_for_real_people_carry_a_caveat():
    """Each caveat here is a failure actually observed in a beta session."""
    for key in ("instagram", "soundcloud", "youtube", "meta"):
        assert BY_KEY[key].caveat, f"{key} has a known silent-failure mode; say it"


# ── Ordering ────────────────────────────────────────────────────────────────

def test_order_puts_recommended_first_then_cheapest():
    keys = [p.key for p in ordered_for_setup(set())]
    n = len(RECOMMENDED)
    assert set(keys[:n]) == set(RECOMMENDED), (
        f"the recommended group is not on top: {keys[:n]}")
    rest = [BY_KEY[k].effort_min for k in keys[n:]]
    assert rest == sorted(rest), "after the recommended group, cheapest first"


# ── Les trois colonnes du sélecteur ─────────────────────────────────────────

def test_the_three_columns_partition_the_registry():
    """Chaque plateforme dans une colonne et une seule — sinon une case disparaît.

    C'est la propriété qu'une liste de clés écrite à la main perd en silence : elle
    reste juste le jour où on l'écrit, et le jour où quelqu'un ajoute une plateforme
    elle en oublie une sans que rien ne le dise. La dérivation ne le peut pas ; ce
    test le prouve plutôt que de le supposer.
    """
    from src.dashboard.content.platform_value import SETUP_COLUMN_ORDER, setup_columns

    groups = setup_columns(set())
    assert set(groups) == set(SETUP_COLUMN_ORDER), "une colonne a disparu du rendu"
    placed = [pv.key for col in SETUP_COLUMN_ORDER for pv in groups[col]]
    assert sorted(placed) == sorted(p.key for p in PLATFORM_VALUES), (
        f"partition incomplète ou en double : {placed}")


def test_each_column_holds_what_its_title_promises():
    """Le titre d'une colonne est une promesse sur le GESTE qu'elle demande."""
    from src.dashboard.content.platform_value import (
        COLUMN_CSV, COLUMN_LONGER, COLUMN_QUICK, setup_columns,
    )

    g = setup_columns(set())
    assert {p.key for p in g[COLUMN_QUICK]} == set(RECOMMENDED)
    assert all(p.where == CREDENTIALS for p in g[COLUMN_LONGER]), (
        "« un peu plus long » contient un import de fichier")
    assert all(p.where == CSV for p in g[COLUMN_CSV]), (
        "« par fichier » contient une plateforme qui se connecte par identifiant")
    assert {p.key for p in g[COLUMN_CSV]} == {"s4a", "apple_music"}, (
        "les deux imports CSV sont Spotify for Artists et Apple Music")


def test_a_hardcoded_column_would_have_missed_the_new_platform():
    """Mutation : les trois listes de clés qu'on aurait pu écrire à la main.

    Elles étaient justes avant l'ajout de Spotify for Artists. Sans cette assertion,
    les deux tests au-dessus passeraient aussi bien sur une partition figée — donc
    sur la forme qui produit le défaut, pas sur celle qui l'empêche.
    """
    from src.dashboard.content.platform_value import SETUP_COLUMN_ORDER, setup_columns

    frozen = {
        "quick": ["spotify", "instagram", "soundcloud"],
        "longer": ["youtube", "meta"],
        "csv": ["apple_music"],
    }
    missed = {p.key for p in PLATFORM_VALUES} - {k for v in frozen.values() for k in v}
    assert missed, (
        "la partition figée couvre encore tout le registre — la mutation ne reproduit "
        "plus le défaut ; vérifie qu'une plateforme a bien été ajoutée depuis")
    live = setup_columns(set())
    assert not (missed - {pv.key for c in SETUP_COLUMN_ORDER for pv in live[c]}), (
        "la dérivation en oublie autant que la liste figée")


def test_connected_platforms_sink_to_the_bottom():
    """Connected → last, and the CHEAPEST of the ones left leads.

    It named Instagram until 2026-09-04, which was a fact of the two-platform pair
    and not the rule: with SoundCloud recommended too, the next thing to offer after
    Spotify is the two-minute one, not the five-minute one. Naming the winner rather
    than the reason is how a test starts arguing for the old data.
    """
    keys = [p.key for p in ordered_for_setup({"spotify"})]
    assert keys[-1] == "spotify"
    left = [k for k in RECOMMENDED if k != "spotify"]
    assert keys[0] in left, "a recommended platform no longer leads"
    assert BY_KEY[keys[0]].effort_min == min(BY_KEY[k].effort_min for k in left), (
        "the recommended platform on top is not the cheapest one still to do")


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
