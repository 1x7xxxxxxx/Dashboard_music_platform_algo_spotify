"""Stripe webhook handler — Brick 21.

Endpoint: POST /webhooks/stripe
No JWT auth — Stripe signs the payload instead.

Required env vars:
    STRIPE_SECRET_KEY          — sk_live_... or sk_test_...
    STRIPE_WEBHOOK_SECRET      — whsec_... (from Stripe dashboard → Webhooks)

Events handled:
    checkout.session.completed      → provision subscription, then replay the events that
                                      arrived before it (src/utils/stripe_unmatched.py)
    customer.subscription.created   → fill the period dates (never the status)
    customer.subscription.updated   → sync status + period dates

Stripe does not promise delivery order (2026-10-04: an invoice.paid delivered before its
checkout matched no row, answered 200, and its referral month was lost). An invoice.paid
or a customer.subscription.created/updated whose customer has no row yet is PARKED, and
the checkout replays it in the same transaction. Nothing below the endpoint commits: the
endpoint commits once per event.
    customer.subscription.deleted   → mark canceled
    invoice.payment_failed          → mark past_due
    invoice.paid                    → referral reward: earned on a first payment, applied
                                      as a coupon (src/utils/referral_rewards.py, R272)
    charge.refunded / charge.dispute.created → a pending reward dropped; an applied one
                                      KEPT and journaled with the reason (R370 g)
"""
import logging
import os

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["stripe"])


def _get_db():
    """Open a direct psycopg2 connection (no PostgresHandler dependency).

    Returns None on failure, and that stays deliberate here: a webhook must
    answer Stripe rather than raise into the ASGI stack, and the caller already
    treats None as "retry me". The DSN itself is not this module's business —
    `src.utils.pg_connect` resolves DATABASE_URL, then the env vars, then
    config.yaml, which is a superset of what this function used to do.
    """
    from src.utils.pg_connect import connect

    try:
        return connect()
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return None


def _subscription_period(sub: dict) -> tuple:
    """Return (current_period_start, current_period_end) as unix timestamps.

    Stripe API version 2025-…/2026-…dahlia moved these fields off the Subscription
    object onto each subscription item, so the legacy top-level keys are absent on
    customer.subscription.* events. Fall back to the first item's period when missing.
    """
    start = sub.get("current_period_start")
    end = sub.get("current_period_end")
    if start is None or end is None:
        items = (sub.get("items") or {}).get("data") or []
        if items:
            it = items[0]
            start = start if start is not None else it.get("current_period_start")
            end = end if end is not None else it.get("current_period_end")
    return start, end


def _known_customer(cur, stripe_customer_id) -> bool:
    """Does a subscription row carry this Stripe customer yet? Read under `lock_customer`."""
    if not stripe_customer_id:
        return False
    cur.execute("SELECT 1 FROM artist_subscriptions WHERE stripe_customer_id = %s",
                (stripe_customer_id,))
    return cur.fetchone() is not None


def _upsert_subscription(cur, data: dict, fill_only: bool = False) -> None:
    """Write a customer.subscription.* event onto the row matched by stripe_customer_id.

    Never commits: the endpoint commits once per event. `fill_only` (the `.created` event)
    only fills what is still empty and never touches the status, so a late or replayed
    creation (status `incomplete`) cannot undo the `active` the checkout already wrote.
    """
    p_start, p_end = _subscription_period(data)
    if fill_only:
        cur.execute(
            """
            UPDATE artist_subscriptions SET
                stripe_subscription_id = COALESCE(stripe_subscription_id, %s),
                current_period_start = COALESCE(current_period_start, to_timestamp(%s)),
                current_period_end = COALESCE(current_period_end, to_timestamp(%s)),
                updated_at = NOW()
            WHERE stripe_customer_id = %s
            """,
            (data.get("id"), p_start, p_end, data.get("customer")),
        )
        return
    cur.execute(
        """
        UPDATE artist_subscriptions
        SET
            stripe_subscription_id = %s,
            status = %s,
            current_period_start = to_timestamp(%s),
            current_period_end = to_timestamp(%s),
            cancel_at_period_end = %s,
            updated_at = NOW()
        WHERE stripe_customer_id = %s
          AND (stripe_subscription_id IS NULL OR stripe_subscription_id = %s)
        """,
        (data.get("id"), data.get("status", "active"), p_start, p_end,
         data.get("cancel_at_period_end", False), data.get("customer"),
         data.get("id")),
    )


def _verified_artist_id(conn, claimed, data: dict):
    """L'identifiant réclamé, s'il appartient bien à l'e-mail qui a payé. Sinon `None`.

    Trois refus, chacun pour une raison distincte :

    * l'identifiant n'est pas un entier — un lien bricolé ;
    * il ne désigne aucun locataire — provisionner lèverait une violation de clé
      étrangère, donc un 500, donc un rejeu Stripe pendant trois jours : carte débitée,
      plan jamais posé ;
    * aucun compte de CE locataire ne porte l'e-mail du checkout — c'est le cas
      malveillant, et le seul que la signature Stripe ne peut pas voir.

    Rendre `None` fait retomber le handler sur sa branche « rien à faire », qui répond
    200 : on n'invite pas Stripe à rejouer un événement qu'on refuse délibérément.
    """
    try:
        aid = int(claimed)
    except (TypeError, ValueError):
        logger.warning("Stripe: client_reference_id non entier — événement ignoré")
        return None

    email = (data.get("customer_email")
             or (data.get("customer_details") or {}).get("email") or "").strip().lower()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM saas_artists WHERE id = %s", (aid,))
    if cur.fetchone() is None:
        logger.warning("Stripe: locataire %s inconnu — événement ignoré", aid)
        return None
    if not email:
        # Sans e-mail on ne peut rien apparier. On refuse plutôt que de faire confiance :
        # le mode « lien de paiement » de Stripe fournit toujours `customer_details`.
        logger.warning("Stripe: aucun e-mail dans la session — locataire %s ignoré", aid)
        return None
    cur.execute(
        "SELECT 1 FROM saas_users WHERE artist_id = %s AND lower(email) = %s LIMIT 1",
        (aid, email))
    if cur.fetchone() is None:
        logger.warning(
            "Stripe: l'e-mail payeur n'appartient à aucun compte du locataire %s — "
            "événement ignoré", aid)
        return None
    return aid


@router.post("/stripe", summary="Stripe webhook receiver")
async def stripe_webhook(request: Request):
    """Verify Stripe signature and process billing events."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Signature verification (skip if secret not configured — dev only)
    event = None
    if webhook_secret:
        try:
            import stripe
            import json
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            # Verify the signature (raises on tampering), then use a plain dict for
            # the logic below: construct_event returns a stripe.Event (StripeObject)
            # whose attribute access does NOT expose dict.get() — calling .get() on it
            # raises AttributeError. json.loads on the already-verified raw payload
            # gives an ordinary dict so the .get(...) accessors work.
            stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            event = json.loads(payload)
        except Exception as e:
            logger.warning(f"Stripe signature verification failed: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
    elif os.getenv("STRIPE_ALLOW_UNSIGNED") == "1":
        import json
        logger.warning("STRIPE_WEBHOOK_SECRET not set — accepting UNSIGNED payload "
                       "(dev only, STRIPE_ALLOW_UNSIGNED=1)")
        event = json.loads(payload)
    else:
        # Fail closed: a public endpoint that trusts unsigned Stripe payloads lets
        # anyone forge subscription events (e.g. self-provision Premium for free).
        logger.error("STRIPE_WEBHOOK_SECRET not configured — refusing unsigned webhook")
        raise HTTPException(status_code=503, detail="Webhook signature not configured")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    logger.info(f"Stripe event: {event_type}")

    conn = _get_db()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        _dispatch(conn, event_type, data, event.get("id", ""), event.get("created"))
        # THE single commit of a webhook event: the park, the provisioning, the replay and
        # `replayed_at` land together or not at all (Stripe retries a 5xx).
        conn.commit()
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        conn.close()

    return {"received": True}


def _dispatch(conn, event_type: str, data: dict, event_id: str, created) -> None:
    """Route one event. Nothing here commits — `stripe_webhook` does, once."""
    from src.utils import stripe_unmatched

    cur = conn.cursor()
    try:
        if event_type == "checkout.session.completed":
            _checkout_completed(conn, cur, data)
        elif event_type in ("invoice.paid", *stripe_unmatched.SUBSCRIPTION_EVENTS):
            stripe_unmatched.lock_customer(cur, data.get("customer"))
            _handle_resolvable(cur, event_type, data, event_id, created)
        elif event_type == "customer.subscription.deleted":
            _mark_status(cur, data.get("customer"), data.get("id"), "canceled", event_type)
        elif event_type in ("charge.refunded", "charge.dispute.created"):
            # A refund or a chargeback on the referred artist's payment revokes the reward it
            # earned (security-specialist, R272): pending → deleted, applied → KEPT with the
            # reason until the coupon removal is verified in Stripe test mode. An unknown customer is left alone ON
            # PURPOSE and not parked: it has no reward to take back yet, and replaying a
            # refund after its checkout would revoke a month the order never earned.
            from src.utils.referral_rewards import revoke, stripe_remove
            revoke(cur, data.get("customer"), stripe_remove)
        elif event_type == "invoice.payment_failed":
            _mark_status(cur, data.get("customer"), _invoice_subscription(data), "past_due",
                         event_type)
    finally:
        cur.close()


def _invoice_subscription(invoice: dict):
    """The subscription an invoice bills: `parent.subscription_details.subscription` since
    API 2025-03-31.basil, `invoice.subscription` before it."""
    details = (invoice.get("parent") or {}).get("subscription_details") or {}
    return details.get("subscription") or invoice.get("subscription")


def _mark_status(cur, customer, subscription, status: str, event_type: str) -> None:
    """customer.subscription.deleted / invoice.payment_failed — NOT parked: replaying a
    cancellation or a failure after the checkout would undo the checkout. A 0-row update is
    said, never silent. Keyed by SUBSCRIPTION (R370 d): a late `deleted` for a customer's
    previous subscription must not cancel the one they took since. The customer alone
    matches only a row whose subscription id is not known yet."""
    cur.execute("UPDATE artist_subscriptions SET status = %s, updated_at = NOW() "
                "WHERE stripe_customer_id = %s AND (stripe_subscription_id IS NULL "
                "OR stripe_subscription_id = %s)", (status, customer, subscription))
    if cur.rowcount == 0:
        logger.warning("Stripe %s: customer %s / subscription %s matches no subscription "
                       "row — ignored", event_type, customer, subscription)
    else:
        logger.info(f"Stripe {event_type}: customer={customer} sub={subscription} → {status}")


def _handle_resolvable(cur, event_type: str, data: dict, event_id: str, created) -> None:
    """invoice.paid and customer.subscription.created/updated — the events that need the
    customer's row. Run live (under `lock_customer`) AND on replay, through the same code:
    an event whose customer is not known yet is parked, never dropped."""
    from src.utils import stripe_unmatched
    from src.utils.referral_rewards import UNKNOWN_CUSTOMER, is_first_payment, on_invoice_paid

    if event_type == "invoice.paid":
        # R272: earned on the referred artist's FIRST payment, applied as a coupon on the
        # referrer's subscription, once per referral whatever Stripe retries.
        if on_invoice_paid(cur, data, event_id) != UNKNOWN_CUSTOMER:
            return
        if is_first_payment(data):
            stripe_unmatched.park(cur, event_id, event_type, data, created)
        else:
            logger.warning("Stripe invoice.paid (%s) for unknown customer %s — nothing to "
                           "replay, ignored", data.get("billing_reason"), data.get("customer"))
        return
    if not _known_customer(cur, data.get("customer")):
        p_start, p_end = _subscription_period(data)
        resolved = {**data, "current_period_start": p_start, "current_period_end": p_end}
        stripe_unmatched.park(cur, event_id, event_type, resolved, created)
        return
    _upsert_subscription(cur, data, fill_only=(event_type == "customer.subscription.created"))


def _checkout_completed(conn, cur, data: dict) -> None:
    """Provision the subscription, then replay what arrived before it — one transaction."""
    from src.utils import stripe_unmatched

    customer_id = data.get("customer")
    # Payment Links pass the tenant via client_reference_id (?client_reference_id=…);
    # API-created sessions may instead set metadata.artist_id. Accept both.
    artist_id = data.get("client_reference_id") or data.get("metadata", {}).get("artist_id")
    # LE PAYEUR NE CHOISIT PAS LE LOCATAIRE À PROVISIONNER.
    #
    # `client_reference_id` arrive du lien de paiement, construit côté client et
    # modifiable dans la barre d'adresse. La signature Stripe passe — elle
    # relaie fidèlement ce que le payeur a mis. Sans appariement, un locataire A
    # pouvait activer PUIS révoquer l'abonnement d'un locataire V (l'`ON CONFLICT
    # (artist_id)` écrasait la ligne de V avec le client Stripe de A), et V, s'il
    # payait réellement, cessait d'être synchronisé en silence : ses propres
    # événements ne matchaient plus aucune ligne.
    #
    # On apparie donc l'identifiant à l'e-mail réellement payé. C'est la même
    # classe que « le lien de paiement non attribuable » du 2026-08-23, fermée
    # alors sur les deux surfaces d'ÉMISSION et pas sur celle de RÉCEPTION.
    artist_id = _verified_artist_id(conn, artist_id, data)
    plan_name = data.get("metadata", {}).get("plan_name", "premium")
    if plan_name == "basic":          # retired tier → premium
        plan_name = "premium"
    if not (artist_id and customer_id):
        return
    # Taken BEFORE the row is written: an invoice.paid for this customer either committed
    # its park before us (replayed below) or waits on the lock and then finds the row.
    stripe_unmatched.lock_customer(cur, customer_id)
    _provision(cur, int(artist_id), plan_name, customer_id, data.get("subscription"))
    for parked_id, event_id, event_type, payload in stripe_unmatched.waiting(cur, customer_id):
        _handle_resolvable(cur, event_type, payload, event_id, None)
        stripe_unmatched.mark_replayed(cur, parked_id)
        logger.info("Stripe %s %s replayed after checkout", event_type, event_id)


def _provision(cur, artist_id: int, plan_name: str, customer_id, subscription_id) -> None:
    cur.execute("SELECT id FROM subscription_plans WHERE name = %s", (plan_name,))
    plan_row = cur.fetchone()
    plan_id = plan_row[0] if plan_row else 1
    cur.execute(
        """
        INSERT INTO artist_subscriptions
            (artist_id, plan_id, stripe_customer_id, stripe_subscription_id, status)
        VALUES (%s, %s, %s, %s, 'active')
        ON CONFLICT (artist_id) DO UPDATE SET
            plan_id = EXCLUDED.plan_id,
            stripe_customer_id = EXCLUDED.stripe_customer_id,
            stripe_subscription_id = EXCLUDED.stripe_subscription_id,
            status = 'active',
            updated_at = NOW()
        """,
        (artist_id, plan_id, customer_id, subscription_id),
    )
    # Also update saas_artists.tier
    _tier = plan_name if plan_name in ('free', 'premium') else 'premium'
    cur.execute("UPDATE saas_artists SET tier = %s WHERE id = %s", (_tier, artist_id))
    # Audit the plan transition for the Alerts plan-evolution chart.
    cur.execute(
        "INSERT INTO subscription_plan_history (artist_id, plan, source) "
        "VALUES (%s, %s, 'stripe_webhook')",
        (artist_id, _tier),
    )
    logger.info(f"Subscription provisioned: artist_id={artist_id} plan={plan_name}")
