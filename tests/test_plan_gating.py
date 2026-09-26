"""Plan-gating contract — the highest revenue-risk path (free vs premium).

The dashboard locks pages via this exact predicate in app.show_navigation_menu:

    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible
    locked = not (is_all or key in ALWAYS_ACCESSIBLE or key in accessible)

`_is_locked` itself is a closure (not importable), so we replicate the one-line
predicate over the REAL data (PLAN_FEATURES / ALWAYS_ACCESSIBLE) — a typo that leaks a
premium page into the free allowlist, or breaks the premium '*', fails here. DB-free,
so unlike the render-smoke harness this actually runs in CI.
"""
from src.database.stripe_schema import (
    ALWAYS_ACCESSIBLE,
    PLAN_FEATURES,
    PLAN_RANK,
    _FREE_FEATURES,
    normalize_plan,
)

# ADR-029 (2026-09-26) : TES DONNÉES SONT GRATUITES, LES PRÉDICTIONS SONT PAYANTES.
# Pages that MUST stay behind the paywall — the ones that PREDICT: Road to Algo, the CPR
# optimizer (it reads `ml_song_predictions`) and revenue forecasts.
# ⚠️ Un sous-ensemble assumé des vues du produit : les pages facturées. Une page premium
# NEUVE n'y entre pas toute seule ; c'est le prix de l'énumération, et il se paie en la
# relisant quand on ajoute une page.
KNOWN_PREMIUM_PAGES = {"revenue_forecast", "meta_cpr_optimizer", "trigger_algo"}

# And the other side of the decision, pinned just as hard: pages that READ the artist's
# own data (their fusion included) and the free preview of Road to Algo must stay OPEN to
# Free. A sous-ensemble too: the pages ADR-029 moved, not every free page. Re-locking one of them is a pricing decision, not a refactor — it fails here.
KNOWN_FREE_DATA_PAGES = {"meta_x_spotify", "meta_creatives", "meta_breakdowns",
                         "meta_ads_overview", "export_pdf", "algo_preview"}


def test_the_data_and_the_preview_stay_free() -> None:
    for key in KNOWN_FREE_DATA_PAGES:
        assert not _is_locked("free", key), (
            f"{key!r} is locked for Free — ADR-029 made the artist's data and its fusion free")


def test_the_weekly_report_stays_a_paid_capability() -> None:
    from src.database.stripe_schema import PLAN_CAPABILITIES
    assert "weekly_digest" in PLAN_CAPABILITIES["premium"]
    assert "weekly_digest" not in PLAN_CAPABILITIES.get("free", frozenset())


def _is_locked(plan: str, key: str) -> bool:
    """Mirror of app._is_locked over the real plan data."""
    accessible = PLAN_FEATURES.get(normalize_plan(plan), set())
    is_all = "*" in accessible
    return not (is_all or key in ALWAYS_ACCESSIBLE or key in accessible)


def test_premium_plan_is_unrestricted():
    assert PLAN_FEATURES["premium"] == {"*"}


def test_free_plan_has_no_wildcard():
    assert "*" not in PLAN_FEATURES["free"]


def test_free_user_is_locked_out_of_every_premium_page():
    for key in KNOWN_PREMIUM_PAGES:
        assert _is_locked("free", key), f"PAYWALL BYPASS: free can reach premium page {key!r}"


def test_premium_user_can_reach_every_premium_page():
    for key in KNOWN_PREMIUM_PAGES:
        assert not _is_locked("premium", key), f"premium wrongly locked out of {key!r}"


def test_free_user_can_reach_free_pages():
    for key in _FREE_FEATURES:
        assert not _is_locked("free", key), f"free page {key!r} wrongly locked for free user"


def test_always_accessible_pages_never_locked():
    for plan in ("free", "premium"):
        for key in ALWAYS_ACCESSIBLE:
            assert not _is_locked(plan, key), f"{key!r} should always be accessible ({plan})"


def test_no_premium_page_leaked_into_free_allowlist():
    # The revenue-leak direction: a premium key accidentally added to _FREE_FEATURES.
    assert KNOWN_PREMIUM_PAGES.isdisjoint(_FREE_FEATURES)


def test_normalize_plan_collapses_basic_to_premium():
    assert normalize_plan("basic") == "premium"
    assert normalize_plan("free") == "free"
    assert normalize_plan("premium") == "premium"
    assert normalize_plan(None) == "free"


def test_legacy_basic_still_gets_premium_access():
    # PLAN_RANK keeps basic == premium until migration 048 rewrites the rows; a 'basic'
    # value must never drop a paying-equivalent user to free gating.
    assert PLAN_RANK["basic"] == PLAN_RANK["premium"] > PLAN_RANK["free"]
    assert not _is_locked("basic", "revenue_forecast")
