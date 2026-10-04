"""The referral reward, applied through Stripe: earned on the referred artist's FIRST
payment, credited as a one-month coupon on the referrer's subscription.

Type: Core
Uses: psycopg2 cursor (the webhook's connection), a `stripe_apply(sub_id, coupon_id)` callable
Depends on: referral_rewards (migration 143), referral_events, artist_subscriptions,
            saas_artists.referral_free_months, env STRIPE_REFERRAL_COUPON_ID
Triggers: src/api/routers/stripe_webhook.py (`invoice.paid`, and its replay at checkout)
Persists in: referral_rewards, saas_artists.referral_free_months

R272 (owner decision 2026-09-27 : « l'appliquer via Stripe » ; code-critic verdict a).
Until tonight the month was CREDITED at sign-up and consumed by nobody: the pages had to
say « écris-nous, on l'applique à la main ».

The rules, each one a failure the critic named before this was written:
- **Earned on the first PAYMENT, not the sign-up** — `billing_reason = subscription_create`:
  a referral who never pays earns nothing, and a renewal is not a first payment.
- **Once** — Stripe retries a webhook until it gets a 2xx. `earned_event_id` and
  `referred_artist_id` are UNIQUE in the table: a second delivery changes nothing.
- **One coupon at a time** — a 100 %-off `once` coupon discounts the NEXT invoice; two at
  once would not give two months. The next pending reward is applied only after the
  referrer's invoice carrying the previous one is paid (`applied` → `consumed`).
- **A referrer without a subscription keeps the reward pending** — it is applied on their
  own first paid invoice, never lost.
- **No coupon configured → pending, said** — `STRIPE_REFERRAL_COUPON_ID` absent is not an
  error the payer sees; the admin page lists what is owed.
- `saas_artists.referral_free_months` = months earned and NOT yet applied: +1 when earned,
  −1 when applied. It is what the artist's pages show.
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

FIRST_PAYMENT = "subscription_create"

# What `on_invoice_paid` returns when the payer's customer matches no subscription row yet:
# the router parks the event instead of answering 200 over a lost month (2026-10-04).
UNKNOWN_CUSTOMER = "unknown_customer"


def coupon_id() -> Optional[str]:
    return os.getenv("STRIPE_REFERRAL_COUPON_ID") or None


def _artist_of_customer(cur, customer_id) -> Optional[int]:
    if not customer_id:
        return None
    cur.execute("SELECT artist_id FROM artist_subscriptions WHERE stripe_customer_id = %s",
                (customer_id,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def _same_person(cur, a: int, b: int) -> bool:
    """Two accounts of one person: same Stripe customer, or the same mailbox once the
    `+tag` is dropped (security-specialist, R272 — self-referral to farm months)."""
    if a == b:
        return True
    cur.execute("SELECT stripe_customer_id FROM artist_subscriptions WHERE artist_id IN (%s, %s) "
                "AND stripe_customer_id IS NOT NULL", (a, b))
    customers = [r[0] for r in cur.fetchall()]
    if len(customers) != len(set(customers)):
        return True
    cur.execute("SELECT artist_id, lower(split_part(email, '@', 1)), lower(split_part(email, '@', 2)) "
                "FROM saas_users WHERE artist_id IN (%s, %s) AND email IS NOT NULL", (a, b))
    boxes = {}
    for artist, local, domain in cur.fetchall():
        boxes.setdefault(artist, set()).add((local.split("+")[0].replace(".", "")
                                             if domain in ("gmail.com", "googlemail.com")
                                             else local.split("+")[0], domain))
    return bool(boxes.get(a, set()) & boxes.get(b, set()))


def is_first_payment(invoice: dict) -> bool:
    """THE definition of a first payment — read by `earn` and by the router's park decision.

    A 0 € first invoice (a trial, a 100 % promo code) is not a payment: it earns nothing
    (security-specialist, R272, HIGH).
    """
    return (invoice.get("billing_reason") == FIRST_PAYMENT
            and (invoice.get("amount_paid") or 0) > 0)


def earn(cur, invoice: dict, event_id: str) -> Optional[int]:
    """Record the reward a first payment earns. Returns the referrer, or None."""
    if not is_first_payment(invoice) or not event_id:
        return None
    referred = _artist_of_customer(cur, invoice.get("customer"))
    if referred is None:
        return None
    cur.execute("SELECT referrer_artist_id FROM referral_events "
                "WHERE referred_artist_id = %s ORDER BY id LIMIT 1", (referred,))
    row = cur.fetchone()
    if not row or _same_person(cur, int(row[0]), referred):
        return None
    referrer = int(row[0])
    cur.execute(
        "INSERT INTO referral_rewards (referrer_artist_id, referred_artist_id, earned_event_id) "
        "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
        (referrer, referred, event_id))
    if cur.fetchone() is None:
        return None                          # already earned — a retried delivery
    cur.execute("UPDATE saas_artists SET referral_free_months = "
                "COALESCE(referral_free_months, 0) + 1 WHERE id = %s", (referrer,))
    return referrer


def consume(cur, invoice: dict) -> int:
    """The referrer's paid invoice used the coupon applied before it. Returns rows marked."""
    artist = _artist_of_customer(cur, invoice.get("customer"))
    coupon = coupon_id()
    # Only OUR coupon counts as the month being used — another discount on the same invoice
    # is not the referral month (security-specialist, R272, LOW).
    import json
    carried = json.dumps([invoice.get("discount"), invoice.get("discounts"),
                          invoice.get("total_discount_amounts")], default=str)
    if artist is None or not coupon or coupon not in carried:
        return 0
    cur.execute("UPDATE referral_rewards SET status = 'consumed', consumed_at = now() "
                "WHERE referrer_artist_id = %s AND status = 'applied'", (artist,))
    return cur.rowcount or 0


def apply_next(cur, referrer: int, stripe_apply: Callable[..., None],
               coupon: Optional[str] = None) -> Optional[int]:
    """Apply ONE pending reward to the referrer's subscription, if nothing is applied yet.

    Returns the reward applied, or None (no coupon, no subscription, one already applied,
    nothing pending). Never raises on Stripe's side: the reward stays pending with why.
    """
    coupon = coupon or coupon_id()
    if not coupon:
        return None
    # ONE application at a time per referrer, even with two webhooks in flight: the
    # referrer's row is the lock (security-specialist, R272 — two `applied` rows for one
    # coupon, the counter down by two).
    cur.execute("SELECT 1 FROM saas_artists WHERE id = %s FOR UPDATE", (referrer,))
    cur.execute("SELECT 1 FROM referral_rewards WHERE referrer_artist_id = %s "
                "AND status = 'applied'", (referrer,))
    if cur.fetchone():
        return None                          # the previous month has not been billed yet
    cur.execute("SELECT stripe_subscription_id FROM artist_subscriptions WHERE artist_id = %s "
                "AND status IN ('active', 'trialing') AND stripe_subscription_id IS NOT NULL",
                (referrer,))
    sub = cur.fetchone()
    if not sub:
        return None                          # pending until the referrer subscribes
    cur.execute("SELECT id FROM referral_rewards WHERE referrer_artist_id = %s "
                "AND status = 'pending' ORDER BY id LIMIT 1 FOR UPDATE", (referrer,))
    row = cur.fetchone()
    if not row:
        return None
    reward = int(row[0])
    try:
        stripe_apply(sub[0], coupon, f"referral-reward-{reward}")
    except Exception as exc:                 # noqa: BLE001 — stays pending, says why
        from src.utils.safe_error import safe_error
        cur.execute("UPDATE referral_rewards SET detail = %s WHERE id = %s",
                    (f"stripe: {safe_error(exc)}"[:300], reward))
        logger.error("referral coupon not applied (reward %s): %s", reward, safe_error(exc))
        return None
    cur.execute("UPDATE referral_rewards SET status = 'applied', applied_at = now(), "
                "stripe_subscription_id = %s, coupon_id = %s, detail = NULL WHERE id = %s",
                (sub[0], coupon, reward))
    cur.execute("UPDATE saas_artists SET referral_free_months = "
                "GREATEST(COALESCE(referral_free_months, 0) - 1, 0) WHERE id = %s", (referrer,))
    return reward


def stripe_apply(subscription_id: str, coupon: str, idempotency_key: str = "") -> None:
    """The real Stripe call: the coupon ADDED to the subscription's discounts.

    `discounts=[…]` REPLACES what is there: the referrer's other discounts are read and
    kept. The idempotency key makes a retried webhook set it once (security-specialist).

    The SDK object is converted ONCE, at the boundary: since stripe-python 15 a
    StripeObject is not a dict and `.get` raises AttributeError (R369 — every referral
    coupon failed that way; the webhook paid the same lesson in June, 9493941c).
    `to_dict()` then `[...]` is measured valid from the 8.0.0 floor to 15.5.1.
    Guard: tests/test_stripe_apply_touches_the_real_sdk_object.py.
    """
    import stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    sub = stripe.Subscription.retrieve(subscription_id).to_dict()
    kept = [{"discount": d if isinstance(d, str) else d["id"]}
            for d in (sub.get("discounts") or [])]
    stripe.Subscription.modify(subscription_id, discounts=kept + [{"coupon": coupon}],
                               idempotency_key=idempotency_key or None)


# Whether `stripe_remove` (DELETE /subscriptions/{id}/discount, the legacy SINGULAR
# discount) removes OUR coupon on a subscription that holds several `discounts` entries
# — which is exactly what `stripe_apply` builds — has never been observed in Stripe test
# mode (code-critic, R369). Until it is, an `applied` reward is NOT removed on a refund
# and its row is KEPT with the reason: an unverified irreversible call could delete the
# referrer's other discount, and the DELETE below would erase the only record of it.
# Flip only together with a test that pins the test-mode result.
REMOVE_ON_A_MULTI_DISCOUNT_SUBSCRIPTION_VERIFIED = False


def revoke(cur, customer_id, remove: Callable[[str], None]) -> Optional[str]:
    """A refund or a chargeback on the referred artist's payment takes the month back
    (security-specialist, R272, HIGH). Returns what was done, or None."""
    referred = _artist_of_customer(cur, customer_id)
    if referred is None:
        return None
    cur.execute("SELECT id, referrer_artist_id, status, stripe_subscription_id FROM referral_rewards "
                "WHERE referred_artist_id = %s FOR UPDATE", (referred,))
    row = cur.fetchone()
    if not row:
        return None
    reward, referrer, status, sub = row
    if status == "pending":
        cur.execute("UPDATE saas_artists SET referral_free_months = "
                    "GREATEST(COALESCE(referral_free_months, 0) - 1, 0) WHERE id = %s", (referrer,))
    elif status == "applied" and sub and not REMOVE_ON_A_MULTI_DISCOUNT_SUBSCRIPTION_VERIFIED:
        logger.error("referral reward %s refunded while applied — coupon NOT removed "
                     "(removal unverified, R369): check subscription %s", reward, sub)
        cur.execute("UPDATE referral_rewards SET detail = 'remboursé pendant application — "
                    "retrait du coupon à vérifier (R369)' WHERE id = %s", (reward,))
        return "applied-kept"
    elif status == "applied" and sub:
        remove(sub)
    else:
        logger.warning("referral reward %s already consumed — refund noted, month kept", reward)
        cur.execute("UPDATE referral_rewards SET detail = 'remboursé après consommation' "
                    "WHERE id = %s", (reward,))
        return "consumed"
    cur.execute("DELETE FROM referral_rewards WHERE id = %s", (reward,))
    return status


def stripe_remove(subscription_id: str) -> None:
    import stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    stripe.Subscription.delete_discount(subscription_id)


def on_invoice_paid(cur, invoice: dict, event_id: str,
                    apply: Optional[Callable[..., None]] = None) -> Optional[str]:
    """The whole reward cycle for one paid invoice.

    Returns UNKNOWN_CUSTOMER when the payer matches no subscription row — the caller decides
    whether to park it — and None otherwise. `apply` is resolved at CALL time so a test can
    stub `stripe_apply` on the module.
    """
    if _artist_of_customer(cur, invoice.get("customer")) is None:
        return UNKNOWN_CUSTOMER
    apply = apply or stripe_apply
    consume(cur, invoice)
    referrer = earn(cur, invoice, event_id)
    if referrer is not None:
        apply_next(cur, referrer, apply)
    payer = _artist_of_customer(cur, invoice.get("customer"))
    if payer is not None:                    # the payer may be a referrer owed a month
        apply_next(cur, payer, apply)
    return None
