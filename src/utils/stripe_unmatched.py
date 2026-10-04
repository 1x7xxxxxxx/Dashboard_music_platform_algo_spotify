"""A Stripe event that arrived before the row it needs: parked, then replayed.

Type: Utility
Uses: psycopg2 cursor (the webhook's connection — this module NEVER commits)
Depends on: stripe_unmatched_events (migration 145), artist_subscriptions
Triggers: src/api/routers/stripe_webhook.py (park, replay), airflow/dags/alert_monitor.py
          (`check_billing_sync` → `stale_issues`)
Persists in: stripe_unmatched_events

Every Stripe handler resolves the tenant through `artist_subscriptions.stripe_customer_id`,
and only `checkout.session.completed` writes that row. Stripe does not promise delivery
order: on 2026-10-04 an `invoice.paid` arrived first, matched nothing, answered 200, and the
referral month it earned was lost without a trace.

The three rules (code-critic, BUILD-MODIFIED):
- **One lock per customer.** Stripe delivers concurrently. Without it, `invoice.paid` reads
  no row and parks while an uncommitted checkout reads an empty park list: both commit, the
  park is never replayed. `lock_customer` serialises every transaction that reads or writes
  one customer's row or parked events.
- **Park only what replay gives value to**: a first paid invoice, a subscription created
  or updated. A refund, a deletion or a failed payment for an unknown customer is logged,
  not parked — replaying it after the checkout would undo the checkout.
- **Keep the minimum.** The payload is what the handlers read, never the whole invoice.
"""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Advisory-lock namespace (pg_advisory_xact_lock(int4, int4)) — isolates this lock from
# request_throttle's (0x7A7B). Arbitrary and stable: "ST" for Stripe.
_LOCK_CLASS = 0x5354

# A parked event older than this is reported in the evening mail. NOT calibrated on a
# measured delay: the Stripe account that emitted the 2026-10-04 events is not the one the
# local CLI is logged into, so the real gap between invoice.paid and checkout could not be
# read (2026-10-04). Decision argument instead: Stripe delivers a pair within seconds when
# both succeed; anything still parked after an hour is a checkout that was refused
# (`_verified_artist_id`) or that Stripe is still retrying — both need a human.
STALE_AFTER_HOURS = 1

SUBSCRIPTION_EVENTS = ("customer.subscription.created", "customer.subscription.updated")

# The fields each handler reads — and nothing else (no e-mail, name or address).
_KEPT = {
    "invoice.paid": ("customer", "billing_reason", "amount_paid", "discount", "discounts",
                     "total_discount_amounts"),
    "customer.subscription.created": ("customer", "id", "status", "cancel_at_period_end",
                                      "current_period_start", "current_period_end"),
    "customer.subscription.updated": ("customer", "id", "status", "cancel_at_period_end",
                                      "current_period_start", "current_period_end"),
}


def lock_customer(cur, customer_id: Optional[str]) -> None:
    """Serialise this transaction with every other one touching the same customer."""
    if customer_id:
        cur.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))", (_LOCK_CLASS, customer_id))


def minimal(event_type: str, data: dict) -> dict:
    """The fields replay reads. Subscription periods arrive already resolved by the caller."""
    return {k: data.get(k) for k in _KEPT[event_type]}


def park(cur, event_id: str, event_type: str, data: dict, created) -> None:
    """Keep an event whose customer matched no row. A retried delivery parks nothing new."""
    cur.execute(
        "INSERT INTO stripe_unmatched_events (event_id, event_type, stripe_customer_id, "
        "event_created, payload) VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (event_id) DO NOTHING",
        (event_id, event_type, data.get("customer"), int(created or 0),
         json.dumps(minimal(event_type, data), default=str)))
    logger.warning("Stripe %s for unknown customer %s parked until its checkout",
                   event_type, data.get("customer"))


def waiting(cur, customer_id: str) -> list[tuple]:
    """(id, event_id, event_type, payload) still parked for this customer, oldest first."""
    cur.execute(
        "SELECT id, event_id, event_type, payload FROM stripe_unmatched_events "
        "WHERE stripe_customer_id = %s AND replayed_at IS NULL "
        "ORDER BY event_created, id FOR UPDATE",
        (customer_id,))
    return [(r[0], r[1], r[2], r[3] if isinstance(r[3], dict) else json.loads(r[3]))
            for r in cur.fetchall()]


def mark_replayed(cur, parked_id: int) -> None:
    cur.execute("UPDATE stripe_unmatched_events SET replayed_at = now() WHERE id = %s",
                (parked_id,))


def stale_issues(fetch: Callable[[str, tuple], list], hours: int = STALE_AFTER_HOURS) -> list[dict]:
    """The evening check (alert_monitor.check_billing_sync): parked events nobody replayed,
    shaped like a billing issue. `fetch(sql, params) -> rows` — PostgresHandler.fetch_query."""
    rows = fetch(
        "SELECT stripe_customer_id, event_type, count(*), min(received_at) "
        "FROM stripe_unmatched_events WHERE replayed_at IS NULL "
        "AND received_at < now() - make_interval(hours => %s) "
        "GROUP BY 1, 2 ORDER BY 4",
        (hours,))
    return [{"artist_id": "—", "artist_name": f"client Stripe {customer}",
             "status": "unmatched",
             "reason": (f"{n} évènement(s) {etype} sans abonnement correspondant depuis le "
                        f"{str(first)[:16]} — checkout refusé ou jamais reçu")}
            for customer, etype, n, first in (rows or [])]
