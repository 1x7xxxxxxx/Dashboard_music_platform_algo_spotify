"""Stripe webhook handler — Brick 21.

Endpoint: POST /webhooks/stripe
No JWT auth — Stripe signs the payload instead.

Required env vars:
    STRIPE_SECRET_KEY          — sk_live_... or sk_test_...
    STRIPE_WEBHOOK_SECRET      — whsec_... (from Stripe dashboard → Webhooks)

Events handled:
    checkout.session.completed      → provision subscription
    customer.subscription.updated   → sync status + period dates
    customer.subscription.deleted   → mark canceled
    invoice.payment_failed          → mark past_due
"""
import logging
import os

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["stripe"])


def _get_db():
    """Open a direct psycopg2 connection (no PostgresHandler dependency)."""
    import psycopg2
    from src.utils.config_loader import config_loader

    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return psycopg2.connect(database_url)
        config = config_loader.load()
        db_cfg = config["database"]
        return psycopg2.connect(
            host=db_cfg["host"],
            port=db_cfg["port"],
            database=db_cfg["database"],
            user=db_cfg["user"],
            password=db_cfg["password"],
        )
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return None


def _upsert_subscription(conn, stripe_customer_id: str, stripe_subscription_id: str,
                          status: str, period_start, period_end, cancel_at_period_end: bool):
    """Update artist_subscriptions row matched by stripe_customer_id."""
    cur = conn.cursor()
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
        """,
        (stripe_subscription_id, status, period_start, period_end,
         cancel_at_period_end, stripe_customer_id),
    )
    conn.commit()
    cur.close()


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
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception as e:
            logger.warning(f"Stripe signature verification failed: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        import json
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification (dev mode)")
        event = json.loads(payload)

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    logger.info(f"Stripe event: {event_type}")

    conn = _get_db()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        # ── checkout.session.completed ───────────────────────────────────
        if event_type == "checkout.session.completed":
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            artist_id = data.get("metadata", {}).get("artist_id")
            plan_name = data.get("metadata", {}).get("plan_name", "basic")

            if artist_id and customer_id:
                cur = conn.cursor()
                # Resolve plan id
                cur.execute(
                    "SELECT id FROM subscription_plans WHERE name = %s", (plan_name,)
                )
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
                    (int(artist_id), plan_id, customer_id, subscription_id),
                )
                # Also update saas_artists.tier
                cur.execute(
                    "UPDATE saas_artists SET tier = %s WHERE id = %s",
                    (plan_name if plan_name in ('basic', 'premium') else 'basic', int(artist_id)),
                )
                conn.commit()
                cur.close()
                logger.info(f"Subscription provisioned: artist_id={artist_id} plan={plan_name}")

        # ── customer.subscription.updated ───────────────────────────────
        elif event_type == "customer.subscription.updated":
            _upsert_subscription(
                conn,
                stripe_customer_id=data.get("customer"),
                stripe_subscription_id=data.get("id"),
                status=data.get("status", "active"),
                period_start=data.get("current_period_start"),
                period_end=data.get("current_period_end"),
                cancel_at_period_end=data.get("cancel_at_period_end", False),
            )

        # ── customer.subscription.deleted ───────────────────────────────
        elif event_type == "customer.subscription.deleted":
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE artist_subscriptions
                SET status = 'canceled', updated_at = NOW()
                WHERE stripe_customer_id = %s
                """,
                (data.get("customer"),),
            )
            conn.commit()
            cur.close()
            logger.info(f"Subscription canceled: customer={data.get('customer')}")

        # ── invoice.payment_failed ───────────────────────────────────────
        elif event_type == "invoice.payment_failed":
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE artist_subscriptions
                SET status = 'past_due', updated_at = NOW()
                WHERE stripe_customer_id = %s
                """,
                (data.get("customer"),),
            )
            conn.commit()
            cur.close()
            logger.warning(f"Payment failed: customer={data.get('customer')}")

    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        conn.close()

    return {"received": True}
