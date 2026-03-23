-- 1. Création de la base de données spotify_etl (si elle n'existe pas)
SELECT 'CREATE DATABASE spotify_etl'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'spotify_etl')\gexec

-- 2. Connexion à la nouvelle base
\c spotify_etl

-- ============================================================
-- 3. Tables SaaS multi-tenant (doivent être créées en premier)
-- ============================================================

CREATE TABLE IF NOT EXISTS saas_artists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    tier VARCHAR(20) NOT NULL DEFAULT 'basic'
        CHECK (tier IN ('basic', 'premium')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artist_credentials (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    token_encrypted TEXT,
    extra_config JSONB,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, platform)
);

-- ============================================================
-- 4. Tables Spotify API (core)
-- ============================================================

CREATE TABLE IF NOT EXISTS artists (
    artist_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    followers INTEGER DEFAULT 0,
    popularity INTEGER DEFAULT 0,
    genres TEXT[],
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id VARCHAR(50) PRIMARY KEY,
    track_name VARCHAR(255) NOT NULL,
    artist_id VARCHAR(50) REFERENCES artists(artist_id),
    popularity INTEGER DEFAULT 0,
    duration_ms INTEGER,
    explicit BOOLEAN DEFAULT FALSE,
    album_name VARCHAR(255),
    release_date DATE,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS track_popularity_history (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
    track_id VARCHAR(50) NOT NULL,
    track_name VARCHAR(255) NOT NULL,
    popularity INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date DATE DEFAULT CURRENT_DATE,
    UNIQUE(artist_id, track_id, date)
);

CREATE TABLE IF NOT EXISTS artist_history (
    id SERIAL PRIMARY KEY,
    artist_id VARCHAR(50) REFERENCES artists(artist_id),
    followers INTEGER DEFAULT 0,
    popularity INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 5. Tables SoundCloud (pas de fichier schema dédié)
-- ============================================================

CREATE TABLE IF NOT EXISTS soundcloud_tracks_daily (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
    track_id VARCHAR(50) NOT NULL,
    title VARCHAR(500),
    permalink_url TEXT,
    playback_count INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    reposts_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    collected_at DATE DEFAULT CURRENT_DATE,
    UNIQUE(artist_id, track_id, collected_at)
);

-- ============================================================
-- 6. Tables Instagram (pas de fichier schema dédié)
-- ============================================================

CREATE TABLE IF NOT EXISTS instagram_daily_stats (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
    ig_user_id VARCHAR(50) NOT NULL,
    username VARCHAR(255),
    followers_count INTEGER DEFAULT 0,
    follows_count INTEGER DEFAULT 0,
    media_count INTEGER DEFAULT 0,
    collected_at DATE DEFAULT CURRENT_DATE,
    UNIQUE(artist_id, ig_user_id, collected_at)
);

-- ============================================================
-- 7. Index
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_saas_artists_slug ON saas_artists(slug);
CREATE INDEX IF NOT EXISTS idx_saas_artists_active ON saas_artists(active) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS idx_artist_credentials_artist ON artist_credentials(artist_id);
CREATE INDEX IF NOT EXISTS idx_track_pop_history_track ON track_popularity_history(track_id);
CREATE INDEX IF NOT EXISTS idx_track_pop_history_date ON track_popularity_history(date DESC);
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist_id);
CREATE INDEX IF NOT EXISTS idx_soundcloud_daily_artist ON soundcloud_tracks_daily(artist_id);
CREATE INDEX IF NOT EXISTS idx_soundcloud_daily_date ON soundcloud_tracks_daily(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_instagram_daily_artist ON instagram_daily_stats(artist_id);
CREATE INDEX IF NOT EXISTS idx_instagram_daily_date ON instagram_daily_stats(collected_at DESC);

-- ============================================================
-- 8. iMusician — revenus mensuels
-- ============================================================

CREATE TABLE IF NOT EXISTS imusician_monthly_revenue (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    revenue_eur NUMERIC(10, 2) NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_imusician_artist_month UNIQUE(artist_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_imusician_revenue_artist ON imusician_monthly_revenue(artist_id);
CREATE INDEX IF NOT EXISTS idx_imusician_revenue_period ON imusician_monthly_revenue(year DESC, month DESC);

-- ============================================================
-- 9. ML — Prédictions scoring quotidien
-- ============================================================

CREATE TABLE IF NOT EXISTS ml_song_predictions (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song VARCHAR(255) NOT NULL,
    prediction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    days_since_release INTEGER,
    streams_7d INTEGER,
    streams_28d INTEGER,
    dw_probability FLOAT,
    rr_probability FLOAT,
    radio_probability FLOAT,
    dw_streams_forecast_7d INTEGER,
    rr_streams_forecast_7d INTEGER,
    model_version VARCHAR(50) DEFAULT 'v1',
    features_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_ml_prediction UNIQUE(artist_id, song, prediction_date, model_version)
);

CREATE INDEX IF NOT EXISTS idx_ml_predictions_artist ON ml_song_predictions(artist_id);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_song_date ON ml_song_predictions(artist_id, song, prediction_date DESC);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_date ON ml_song_predictions(prediction_date DESC);

-- ============================================================
-- 10. Artist Wrapped — annual Spotify for Artists metrics
-- ============================================================

CREATE TABLE IF NOT EXISTS artist_wrapped (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    year INTEGER NOT NULL,
    listeners BIGINT,
    streams BIGINT,
    hours_listened DECIMAL(14, 1),
    countries INTEGER,
    listener_gain INTEGER,
    stream_gain BIGINT,
    save_gain INTEGER,
    playlist_add_gain INTEGER,
    saves BIGINT,
    playlist_adds BIGINT,
    top_artist_name VARCHAR(255),
    top_artist_fan_pct DECIMAL(5, 2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_artist_wrapped_year UNIQUE(artist_id, year)
);

CREATE INDEX IF NOT EXISTS idx_artist_wrapped_artist ON artist_wrapped(artist_id);
CREATE INDEX IF NOT EXISTS idx_artist_wrapped_year ON artist_wrapped(artist_id, year DESC);

-- ============================================================
-- 11. Tables S4A (Spotify for Artists CSV)
-- ============================================================

CREATE TABLE IF NOT EXISTS s4a_songs_global (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song VARCHAR(255) NOT NULL,
    listeners INTEGER DEFAULT 0,
    streams INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    release_date DATE,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, song)
);

CREATE TABLE IF NOT EXISTS s4a_song_timeline (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    streams INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, song, date)
);

CREATE TABLE IF NOT EXISTS s4a_audience (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    date DATE NOT NULL,
    listeners INTEGER DEFAULT 0,
    streams INTEGER DEFAULT 0,
    followers INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, date)
);

CREATE INDEX IF NOT EXISTS idx_s4a_songs_song ON s4a_songs_global(song);
CREATE INDEX IF NOT EXISTS idx_s4a_songs_streams ON s4a_songs_global(streams DESC);
CREATE INDEX IF NOT EXISTS idx_s4a_timeline_song ON s4a_song_timeline(song);
CREATE INDEX IF NOT EXISTS idx_s4a_timeline_date ON s4a_song_timeline(date DESC);
CREATE INDEX IF NOT EXISTS idx_s4a_timeline_song_date ON s4a_song_timeline(song, date);
CREATE INDEX IF NOT EXISTS idx_s4a_audience_date ON s4a_audience(date DESC);

-- ============================================================
-- 12. Tables Meta Ads configuration
-- ============================================================

CREATE TABLE IF NOT EXISTS meta_campaigns (
    campaign_id VARCHAR(50) PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    status VARCHAR(50),
    objective VARCHAR(100),
    daily_budget DECIMAL(10, 2),
    lifetime_budget DECIMAL(10, 2),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_time TIMESTAMP,
    updated_time TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_adsets (
    adset_id VARCHAR(50) PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    adset_name VARCHAR(255) NOT NULL,
    campaign_id VARCHAR(50) REFERENCES meta_campaigns(campaign_id),
    status VARCHAR(50),
    optimization_goal VARCHAR(100),
    billing_event VARCHAR(50),
    daily_budget DECIMAL(10, 2),
    lifetime_budget DECIMAL(10, 2),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    targeting JSONB,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_ads (
    ad_id VARCHAR(50) PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_name VARCHAR(255) NOT NULL,
    adset_id VARCHAR(50) REFERENCES meta_adsets(adset_id),
    campaign_id VARCHAR(50) REFERENCES meta_campaigns(campaign_id),
    status VARCHAR(50),
    creative_id VARCHAR(50),
    created_time TIMESTAMP,
    updated_time TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta_insights (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_id VARCHAR(50) REFERENCES meta_ads(ad_id),
    date DATE NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend DECIMAL(10, 2) DEFAULT 0,
    reach INTEGER DEFAULT 0,
    frequency DECIMAL(10, 2) DEFAULT 0,
    cpc DECIMAL(10, 4) DEFAULT 0,
    cpm DECIMAL(10, 4) DEFAULT 0,
    ctr DECIMAL(10, 4) DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    cost_per_conversion DECIMAL(10, 4) DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, ad_id, date)
);

CREATE INDEX IF NOT EXISTS idx_meta_campaigns_name ON meta_campaigns(campaign_name);
CREATE INDEX IF NOT EXISTS idx_meta_campaigns_status ON meta_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_meta_adsets_campaign ON meta_adsets(campaign_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_adset ON meta_ads(adset_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign ON meta_ads(campaign_id);
CREATE INDEX IF NOT EXISTS idx_meta_insights_ad ON meta_insights(ad_id);
CREATE INDEX IF NOT EXISTS idx_meta_insights_date ON meta_insights(date DESC);
CREATE INDEX IF NOT EXISTS idx_meta_insights_ad_date ON meta_insights(ad_id, date);

-- ============================================================
-- 13. Tables Meta Insights (CSV watcher — performance + engagement)
-- ============================================================

CREATE TABLE IF NOT EXISTS meta_insights_performance (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    date_start DATE,
    spend DECIMAL(10, 4) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    frequency DECIMAL(10, 4) DEFAULT 0,
    results INTEGER DEFAULT 0,
    cpr DECIMAL(10, 4) DEFAULT 0,
    cpm DECIMAL(10, 4) DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    cpc DECIMAL(10, 4) DEFAULT 0,
    ctr DECIMAL(10, 4) DEFAULT 0,
    lp_views INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, date_start)
);

CREATE TABLE IF NOT EXISTS meta_insights_performance_day (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    day_date DATE NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0,
    cpr DECIMAL(10, 4) DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, day_date)
);

CREATE TABLE IF NOT EXISTS meta_insights_performance_age (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    age_range VARCHAR(50) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0,
    cpr DECIMAL(10, 4) DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, age_range)
);

CREATE TABLE IF NOT EXISTS meta_insights_performance_country (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0,
    cpr DECIMAL(10, 4) DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, country)
);

CREATE TABLE IF NOT EXISTS meta_insights_performance_placement (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    platform VARCHAR(100) NOT NULL,
    placement VARCHAR(100) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0,
    cpr DECIMAL(10, 4) DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, platform, placement)
);

CREATE TABLE IF NOT EXISTS meta_insights_engagement (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    date_start DATE,
    page_interactions INTEGER DEFAULT 0,
    post_reactions INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, date_start)
);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_day (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    day_date DATE NOT NULL,
    page_interactions INTEGER DEFAULT 0,
    post_reactions INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, day_date)
);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_age (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    age_range VARCHAR(50) NOT NULL,
    page_interactions INTEGER DEFAULT 0,
    post_reactions INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, age_range)
);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_country (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    page_interactions INTEGER DEFAULT 0,
    post_reactions INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, country)
);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_placement (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    platform VARCHAR(100) NOT NULL,
    placement VARCHAR(100) NOT NULL,
    page_interactions INTEGER DEFAULT 0,
    post_reactions INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, platform, placement)
);

CREATE INDEX IF NOT EXISTS idx_mip_artist ON meta_insights_performance(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_campaign ON meta_insights_performance(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mip_date_start ON meta_insights_performance(date_start DESC);
CREATE INDEX IF NOT EXISTS idx_mip_day_artist ON meta_insights_performance_day(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_day_date ON meta_insights_performance_day(day_date DESC);
CREATE INDEX IF NOT EXISTS idx_mie_artist ON meta_insights_engagement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_campaign ON meta_insights_engagement(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mie_date_start ON meta_insights_engagement(date_start DESC);
CREATE INDEX IF NOT EXISTS idx_mie_day_artist ON meta_insights_engagement_day(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_day_date ON meta_insights_engagement_day(day_date DESC);

-- ============================================================
-- 14. Tables YouTube
-- ============================================================

CREATE TABLE IF NOT EXISTS youtube_channels (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    channel_id VARCHAR(255) NOT NULL,
    channel_name VARCHAR(500),
    description TEXT,
    published_at TIMESTAMP,
    subscriber_count INTEGER DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    thumbnail_url TEXT,
    country VARCHAR(10),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_channel_id UNIQUE(channel_id)
);

CREATE TABLE IF NOT EXISTS youtube_channel_history (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    channel_id VARCHAR(255) NOT NULL,
    subscriber_count INTEGER DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, channel_id, (collected_at::date))
);

CREATE TABLE IF NOT EXISTS youtube_videos (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    video_id VARCHAR(255) NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    title TEXT,
    description TEXT,
    published_at TIMESTAMP,
    thumbnail_url TEXT,
    duration VARCHAR(50),
    definition VARCHAR(10),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_video_id UNIQUE(video_id)
);

CREATE TABLE IF NOT EXISTS youtube_video_stats (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    video_id VARCHAR(255) NOT NULL,
    view_count BIGINT DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    favorite_count INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, video_id, (collected_at::date))
);

CREATE TABLE IF NOT EXISTS youtube_playlists (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    playlist_id VARCHAR(255) NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    title TEXT,
    description TEXT,
    video_count INTEGER DEFAULT 0,
    published_at TIMESTAMP,
    thumbnail_url TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_playlist_id UNIQUE(playlist_id)
);

CREATE TABLE IF NOT EXISTS youtube_comments (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    comment_id VARCHAR(255) NOT NULL,
    video_id VARCHAR(255) NOT NULL,
    author VARCHAR(500),
    text TEXT,
    like_count INTEGER DEFAULT 0,
    published_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_comment_id UNIQUE(comment_id)
);

CREATE INDEX IF NOT EXISTS idx_youtube_channels_id ON youtube_channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_youtube_channel_history_channel ON youtube_channel_history(channel_id);
CREATE INDEX IF NOT EXISTS idx_youtube_channel_history_date ON youtube_channel_history(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_youtube_videos_id ON youtube_videos(video_id);
CREATE INDEX IF NOT EXISTS idx_youtube_videos_channel ON youtube_videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_youtube_video_stats_video ON youtube_video_stats(video_id);
CREATE INDEX IF NOT EXISTS idx_youtube_video_stats_date ON youtube_video_stats(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_youtube_comments_video ON youtube_comments(video_id);

-- ============================================================
-- 15. Tables Apple Music (CSV)
-- ============================================================

CREATE TABLE IF NOT EXISTS apple_songs_performance (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song_name VARCHAR(255) NOT NULL,
    album_name VARCHAR(255),
    plays INTEGER DEFAULT 0,
    listeners INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, song_name)
);

CREATE TABLE IF NOT EXISTS apple_daily_plays (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song_name VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    plays INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, song_name, date)
);

CREATE TABLE IF NOT EXISTS apple_listeners (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    date DATE NOT NULL,
    listeners INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, date)
);

CREATE TABLE IF NOT EXISTS apple_songs_history (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song_name VARCHAR(255) NOT NULL,
    plays INTEGER DEFAULT 0,
    shazam_count INTEGER DEFAULT 0,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_apple_songs_perf_name ON apple_songs_performance(song_name);
CREATE INDEX IF NOT EXISTS idx_apple_daily_song ON apple_daily_plays(song_name);
CREATE INDEX IF NOT EXISTS idx_apple_daily_date ON apple_daily_plays(date DESC);
CREATE INDEX IF NOT EXISTS idx_apple_listeners_date ON apple_listeners(date DESC);
CREATE INDEX IF NOT EXISTS idx_apple_history_artist ON apple_songs_history(artist_id);
CREATE INDEX IF NOT EXISTS idx_apple_history_date ON apple_songs_history(date DESC);

-- ============================================================
-- 16. Tables Hypeddit (saisie manuelle campagnes)
-- ============================================================

CREATE TABLE IF NOT EXISTS hypeddit_campaigns (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(artist_id, campaign_name)
);

CREATE TABLE IF NOT EXISTS hypeddit_daily_stats (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    campaign_name VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    visits INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    budget DECIMAL(10, 2) DEFAULT 0,
    ctr DECIMAL(10, 4) DEFAULT 0,
    cost_per_click DECIMAL(10, 4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, campaign_name, date),
    CONSTRAINT fk_hypeddit_campaign
        FOREIGN KEY (campaign_name) REFERENCES hypeddit_campaigns(campaign_name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hypeddit_campaigns_name ON hypeddit_campaigns(campaign_name);
CREATE INDEX IF NOT EXISTS idx_hypeddit_campaigns_active ON hypeddit_campaigns(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_hypeddit_stats_campaign ON hypeddit_daily_stats(campaign_name);
CREATE INDEX IF NOT EXISTS idx_hypeddit_stats_date ON hypeddit_daily_stats(date DESC);

-- ============================================================
-- 17. Tables Stripe billing (Brick 21)
-- ============================================================

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

-- ============================================================
-- 18. Données initiales
-- ============================================================

-- Artiste par défaut (id=1 pour les données existantes single-artist)
INSERT INTO saas_artists (id, name, slug, tier, active)
VALUES (1, 'Artist Default', 'default', 'premium', TRUE)
ON CONFLICT (slug) DO NOTHING;

-- Réinitialiser la séquence au-dessus de l'id max
SELECT setval('saas_artists_id_seq', GREATEST(1, (SELECT MAX(id) FROM saas_artists)));

-- Donnée de test track_popularity_history
INSERT INTO track_popularity_history (artist_id, track_id, track_name, popularity, date)
VALUES (1, 'test_track_001', 'Test Track Initialization', 50, CURRENT_DATE)
ON CONFLICT (artist_id, track_id, date) DO NOTHING;
