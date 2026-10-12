"""The one sentence that says when Premium falls back to Free (R489, R514).

Type: Utility
Uses: src.utils.plan_resolver.premium_horizon, i18n t(), format_date
Depends on: saas_artists, artist_subscriptions, subscription_plans
Persists in: nothing

Shared by « Mon compte » and « Facturation » so the two pages never disagree. Owner X12
(2026-10-11) : the date of return to Free is ALWAYS said — when nothing ends, the line
says so and names why, instead of falling silent. A date that is not true is worse than
none, so the open case never invents one.
"""
from __future__ import annotations

from datetime import datetime

from src.dashboard.utils.date_format import format_date
from src.dashboard.utils.i18n import t


def _open_sentence(why: str) -> str | None:
    """The « sans date de fin » sentence for each source that keeps premium on."""
    if why == "renews":
        return t("billing.premium_renews",
                 "Premium **sans date de fin** — ton abonnement se renouvelle chaque mois "
                 "tant que tu ne le résilies pas.")
    if why == "promo_open":
        return t("billing.premium_promo_open",
                 "Premium **sans date de fin** — accès offert sans échéance.")
    if why == "granted":
        return t("billing.premium_granted",
                 "Premium **sans date de fin** — accès accordé à la main par l'équipe "
                 "streaMLytics, sans échéance.")
    return None


def premium_end_sentence(end: datetime | None, why: str | None) -> str | None:
    """The sentence for a `premium_horizon` result; None only when premium is not on."""
    if why == "ends" and end is not None:
        return t("billing.premium_until", "Premium jusqu'au **{date}**, puis Free.").format(
            date=format_date(end))
    return _open_sentence(why) if why else None


def premium_end_tag(end: datetime | None, why: str | None) -> str | None:
    """« fin le 17/10/2026 » or « sans date de fin », written beside the plan (R537).

    Owner, 2026-10-12 : « juste à côté de mon plan Premium, entre parenthèses, fin le … ».
    None only when premium is not on — a plan that does not end says so, never a date."""
    if why == "ends" and end is not None:
        return t("billing.premium_tag_until", "fin le {date}").format(date=format_date(end))
    return t("billing.premium_tag_open", "sans date de fin") if why else None


def plan_label(plan: str, db, artist_id: int | None) -> str:
    """« Premium (fin le …) » — the plan name with its end, from a live DB handle (R537)."""
    name = plan.capitalize()
    if plan != "premium" or artist_id is None:
        return name
    from src.utils.plan_resolver import premium_horizon
    tag = premium_end_tag(*premium_horizon(db, artist_id))
    return f"{name} ({tag})" if tag else name


def premium_end_line(db, artist_id: int) -> str | None:
    """`premium_end_sentence` for one tenant, from a live DB handle."""
    from src.utils.plan_resolver import premium_horizon
    return premium_end_sentence(*premium_horizon(db, artist_id))
