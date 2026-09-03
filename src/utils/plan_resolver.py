"""Which plan a tenant is on — resolvable from anywhere, not just a Streamlit session.

Type: Utility
Uses: src.database.stripe_schema (normalize_plan) — no streamlit, no session state
Triggers: dashboard auth, weekly_digest
Persists in: nothing

Why this module exists — measured 2026-09-03.

**No Airflow DAG had ever read the plan tables for entitlement.** The full precedence
— promo → active Stripe subscription → legacy `saas_artists.tier` → free — existed
exactly once, inside `src/dashboard/auth.py`, behind `@st.cache_data` and
`st.session_state`. A DAG cannot call it, and `alert_monitor.check_billing_sync` only
ever touches `artist_subscriptions` to flag Stripe drift to the operator: it never
asks whether a tenant may have a feature.

Making the weekly recap a paid feature needed that answer from a DAG, and the choice
was between extracting this and writing a second resolver. **Extracting**, because two
resolutions of one question drift silently in the direction that matters most: a
customer billed for premium who stops receiving what they pay for, or a free tenant
who receives it. Neither shows up on the surface where it is wrong.

`auth.py` keeps its 60 s `@st.cache_data` layer and calls this; the caching stays
where the reruns are. This module imports no streamlit, which is the condition for a
DAG being able to import it at all.

## What is deliberately NOT here

The admin / `_view_as` shortcut. That is a *session* concept — "show me this page as
a free tenant would see it" — and it belongs with the session, not with the tenant's
actual billing state. A DAG asking "may artist 12 have the digest?" must never get
`premium` because someone is previewing something in a browser.
"""
from __future__ import annotations

from datetime import datetime, timezone

_PLAN_SQL = """
    SELECT
        sa.promo_plan,
        sa.promo_plan_expires_at,
        sp.name        AS subscription_plan,
        sa.tier
    FROM saas_artists sa
    LEFT JOIN artist_subscriptions asub
        ON asub.artist_id = sa.id
        AND asub.status IN ('active', 'trialing')
    LEFT JOIN subscription_plans sp ON sp.id = asub.plan_id
    WHERE sa.id = %s
    LIMIT 1
"""


def plan_row(db, artist_id: int):
    """The raw precedence row for one tenant, or None. Parameterised, never f-string."""
    rows = db.fetch_query(_PLAN_SQL, (artist_id,))
    return rows[0] if rows else None


def plan_from_row(row) -> str:
    """`'free'` or `'premium'` from a `plan_row` result.

    Kept separate from the query on purpose: the promo-expiry comparison must be made
    **fresh**, never memoized, or a promo that expired inside the cache window keeps
    granting access. `auth.py` relies on exactly that split — it caches `plan_row` and
    calls this outside the cache.
    """
    from src.database.stripe_schema import normalize_plan

    if not row:
        return "free"
    promo_plan, promo_expires, subscription_plan, tier = row
    if promo_plan and (promo_expires is None
                       or promo_expires > datetime.now(timezone.utc)):
        return normalize_plan(promo_plan)
    if subscription_plan:
        return normalize_plan(subscription_plan)
    if tier:
        return normalize_plan(tier)
    return "free"


def resolve_plan(db, artist_id: int) -> str:
    """`'free'` or `'premium'` for one tenant, from a live DB handle.

    The DAG-callable entry point. Raises nothing of its own: a caller that cannot read
    the database has a bigger problem than an entitlement, and swallowing it here would
    hand back `'free'` — silently downgrading a paying customer.
    """
    return plan_from_row(plan_row(db, artist_id))


def has_capability(db, artist_id: int, capability: str) -> bool:
    """May this tenant use a NON-PAGE feature (a digest, an export, a webhook)?

    Separate from `PLAN_FEATURES`, whose keys are Streamlit page routes by contract
    (`stripe_schema.py`: *"Keys must match page route keys defined in app.py
    show_navigation_menu()"*) and which `tests/test_plan_gating.py` iterates **as
    pages**. Slipping a non-page key in there would break that test for the right
    reason. `PLAN_CAPABILITIES` is the sibling set for everything that is not a page.
    """
    from src.database.stripe_schema import PLAN_CAPABILITIES

    granted = PLAN_CAPABILITIES.get(resolve_plan(db, artist_id), frozenset())
    return capability in granted
