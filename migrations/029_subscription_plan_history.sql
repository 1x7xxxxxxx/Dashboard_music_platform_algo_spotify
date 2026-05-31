-- Migration 029: subscription_plan_history — append-only plan transition log.
-- artist_subscriptions stores only the CURRENT plan (UNIQUE(artist_id), updated
-- in place), so plan changes over time were not recoverable. This table records
-- one row per plan transition (signup, promo/trial grant, Stripe webhook, admin
-- tier edit) to power the "artists per plan over time" chart in the Alerts view.
--
-- It is append-only; rows are never updated. `plan` is the plan in effect AFTER
-- the change. `source` documents what triggered the transition.

CREATE TABLE IF NOT EXISTS subscription_plan_history (
    id         SERIAL      PRIMARY KEY,
    artist_id  INTEGER     NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    plan       VARCHAR(20) NOT NULL,
    source     VARCHAR(40) NOT NULL DEFAULT 'unknown',
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_history_changed_at
    ON subscription_plan_history (changed_at);

CREATE INDEX IF NOT EXISTS idx_plan_history_artist
    ON subscription_plan_history (artist_id, changed_at);

-- One-time backfill: seed a baseline row per existing artist (plan at their
-- signup date) so the Alerts plan-evolution chart is meaningful from day one.
-- The effective plan = active promo_plan, else legacy tier, else 'free'.
-- Idempotent: skips artists that already have any history row.
INSERT INTO subscription_plan_history (artist_id, plan, source, changed_at)
SELECT a.id,
       COALESCE(NULLIF(a.promo_plan, ''), a.tier, 'free'),
       'backfill',
       COALESCE(MIN(u.created_at), a.created_at, NOW())
FROM saas_artists a
LEFT JOIN saas_users u ON u.artist_id = a.id
WHERE NOT EXISTS (
    SELECT 1 FROM subscription_plan_history h WHERE h.artist_id = a.id
)
GROUP BY a.id, a.promo_plan, a.tier, a.created_at;
