"""PostgreSQL schema for Stripe billing — Brick 21."""

STRIPE_SCHEMA = {
    'subscription_plans': """
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
            ('free',    0.00, 1, '["home","spotify","youtube"]'),
            ('basic',   9.90, 3, '["home","spotify","youtube","meta","instagram","soundcloud","apple_music","hypeddit"]'),
            ('premium', 29.90, 10, '["*"]')
        ON CONFLICT (name) DO NOTHING;
    """,

    'artist_subscriptions': """
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

        CREATE INDEX IF NOT EXISTS idx_artist_subscriptions_artist
        ON artist_subscriptions(artist_id);

        CREATE INDEX IF NOT EXISTS idx_artist_subscriptions_stripe_customer
        ON artist_subscriptions(stripe_customer_id);

        CREATE INDEX IF NOT EXISTS idx_artist_subscriptions_status
        ON artist_subscriptions(status);
    """,
}

# Plan feature sets — used by auth.py for feature gating
# Keys must match page route keys defined in app.py show_navigation_menu()
PLAN_FEATURES = {
    'free':  {'home', 'spotify_s4a_combined', 'youtube',
              'meta_ads_overview', 'instagram', 'soundcloud', 'apple_music',
              'hypeddit', 'imusician', 'upload_csv', 'credentials',
              'export_csv', 'data_wrapped', 'meta_mapping'},
    'basic': {'home', 'spotify_s4a_combined', 'youtube',
              'meta_ads_overview', 'instagram', 'soundcloud', 'apple_music',
              'hypeddit', 'imusician', 'upload_csv', 'credentials',
              'export_csv', 'data_wrapped', 'meta_mapping',
              'trigger_algo', 'export_pdf'},
    'premium': {'*'},  # all features including meta_creatives, meta_cpr_optimizer
}

# Pages always accessible regardless of plan (account management + billing)
ALWAYS_ACCESSIBLE = {'account', 'billing'}

PLAN_RANK = {'free': 0, 'basic': 1, 'premium': 2}


def create_stripe_tables():
    """Create subscription_plans and artist_subscriptions tables."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader

    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    try:
        for table_name, sql in STRIPE_SCHEMA.items():
            db.execute_query(sql)
            print(f"✅ {table_name} created/verified")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    create_stripe_tables()
