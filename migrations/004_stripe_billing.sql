-- Migration 004 — Stripe billing tables (Brick 21)
-- Apply: psql -h localhost -p 5433 -U postgres -d spotify_etl -f migrations/004_stripe_billing.sql

CREATE TABLE IF NOT EXISTS subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    stripe_price_id VARCHAR(100),
    price_monthly DECIMAL(8, 2) NOT NULL DEFAULT 0,
    max_artists INTEGER NOT NULL DEFAULT 1,
    features JSONB DEFAULT '[]',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO subscription_plans (name, price_monthly, max_artists, features)
VALUES
    ('free',    0.00, 1,  '["home","spotify","youtube"]'),
    ('basic',   9.90, 3,  '["home","spotify","youtube","meta","instagram","soundcloud","apple_music","hypeddit"]'),
    ('premium', 29.90, 10, '["*"]')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS artist_subscriptions (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES subscription_plans(id),
    stripe_customer_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id)
);

CREATE INDEX IF NOT EXISTS idx_artist_subscriptions_artist ON artist_subscriptions(artist_id);
CREATE INDEX IF NOT EXISTS idx_artist_subscriptions_stripe_customer ON artist_subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_artist_subscriptions_status ON artist_subscriptions(status);
