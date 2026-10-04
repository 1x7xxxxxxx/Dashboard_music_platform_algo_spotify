-- 145 — stripe_unmatched_events : a Stripe event whose customer matched no subscription
-- row yet, kept until `checkout.session.completed` writes that row and replays it.
--
-- Additive only (CREATE TABLE IF NOT EXISTS) — idempotent, safe to replay.
--
-- Why (2026-10-04, test-mode referral run): every Stripe handler resolves the tenant
-- through `artist_subscriptions.stripe_customer_id`, which ONLY checkout.session.completed
-- writes. Stripe does not promise delivery order. An `invoice.paid` delivered before the
-- checkout matched nothing, answered 200, and the referral month it earned was lost with
-- no trace — reward 256 exists only because the event was replayed by hand.
--
-- What is kept is the MINIMUM replay reads (src/utils/stripe_unmatched.py:minimal) — never
-- the whole invoice, which carries the payer's name, e-mail and address.
--
-- `event_created` is Stripe's `event.created` (unix seconds): replay runs in that order,
-- so an older parked `customer.subscription.updated` cannot overwrite a newer state.
CREATE TABLE IF NOT EXISTS stripe_unmatched_events (
    id                 SERIAL PRIMARY KEY,
    event_id           TEXT NOT NULL UNIQUE,
    event_type         TEXT NOT NULL CHECK (event_type IN (
                           'invoice.paid',
                           'customer.subscription.created',
                           'customer.subscription.updated')),
    stripe_customer_id TEXT NOT NULL,
    event_created      BIGINT NOT NULL DEFAULT 0,
    payload            JSONB NOT NULL,
    received_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    replayed_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_stripe_unmatched_events_waiting
    ON stripe_unmatched_events (stripe_customer_id, event_created)
    WHERE replayed_at IS NULL;

COMMENT ON TABLE stripe_unmatched_events IS
    'Évènements Stripe arrivés avant le checkout qui crée la ligne du client, rejoués par '
    'checkout.session.completed. Une ligne non rejouée depuis plus d''une heure est '
    'signalée chaque soir par check_billing_sync. RÉTENTION : 90 jours, purgée par '
    'alert_monitor (nightly_maintenance).';
