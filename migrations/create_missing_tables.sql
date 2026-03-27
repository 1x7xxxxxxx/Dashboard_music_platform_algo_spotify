-- Migration : création des tables manquantes dans spotify_etl
-- Exécuter via :
--   docker exec -i dashboard_music_platform_algo_spotify-postgres-1 \
--     psql -U postgres -d spotify_etl < scripts/create_missing_tables.sql
--
-- Toutes les instructions sont idempotentes (IF NOT EXISTS / ON CONFLICT DO NOTHING).

\c spotify_etl

-- ============================================================
-- 1. iMusician — revenus mensuels
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
-- 2. ML — Prédictions scoring quotidien
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
-- 3. Meta Ads — tables API (meta_ads_schema.py)
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

CREATE INDEX IF NOT EXISTS idx_meta_campaigns_name   ON meta_campaigns(campaign_name);
CREATE INDEX IF NOT EXISTS idx_meta_campaigns_status ON meta_campaigns(status);

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

CREATE INDEX IF NOT EXISTS idx_meta_adsets_campaign ON meta_adsets(campaign_id);

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

CREATE INDEX IF NOT EXISTS idx_meta_ads_adset    ON meta_ads(adset_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign ON meta_ads(campaign_id);

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
    UNIQUE(ad_id, date)
);

CREATE INDEX IF NOT EXISTS idx_meta_insights_ad      ON meta_insights(ad_id);
CREATE INDEX IF NOT EXISTS idx_meta_insights_date    ON meta_insights(date DESC);
CREATE INDEX IF NOT EXISTS idx_meta_insights_ad_date ON meta_insights(ad_id, date);

-- ============================================================
-- 4. Meta Insights CSV — performance (meta_insight_schema.py)
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

CREATE INDEX IF NOT EXISTS idx_mip_artist     ON meta_insights_performance(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_campaign   ON meta_insights_performance(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mip_date_start ON meta_insights_performance(date_start DESC);

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

CREATE INDEX IF NOT EXISTS idx_mip_day_artist   ON meta_insights_performance_day(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_day_campaign ON meta_insights_performance_day(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mip_day_date     ON meta_insights_performance_day(day_date DESC);

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

CREATE INDEX IF NOT EXISTS idx_mip_age_artist   ON meta_insights_performance_age(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_age_campaign ON meta_insights_performance_age(campaign_name);

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

CREATE INDEX IF NOT EXISTS idx_mip_country_artist   ON meta_insights_performance_country(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_country_campaign ON meta_insights_performance_country(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mip_country_country  ON meta_insights_performance_country(country);

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

CREATE INDEX IF NOT EXISTS idx_mip_pl_artist   ON meta_insights_performance_placement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_pl_campaign ON meta_insights_performance_placement(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mip_pl_platform ON meta_insights_performance_placement(platform);

-- ============================================================
-- 5. Meta Insights CSV — engagement (meta_insight_schema.py)
-- ============================================================

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

CREATE INDEX IF NOT EXISTS idx_mie_artist     ON meta_insights_engagement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_campaign   ON meta_insights_engagement(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mie_date_start ON meta_insights_engagement(date_start DESC);

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

CREATE INDEX IF NOT EXISTS idx_mie_day_artist   ON meta_insights_engagement_day(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_day_campaign ON meta_insights_engagement_day(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mie_day_date     ON meta_insights_engagement_day(day_date DESC);

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

CREATE INDEX IF NOT EXISTS idx_mie_age_artist   ON meta_insights_engagement_age(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_age_campaign ON meta_insights_engagement_age(campaign_name);

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

CREATE INDEX IF NOT EXISTS idx_mie_country_artist   ON meta_insights_engagement_country(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_country_campaign ON meta_insights_engagement_country(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mie_country_country  ON meta_insights_engagement_country(country);

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

CREATE INDEX IF NOT EXISTS idx_mie_pl_artist   ON meta_insights_engagement_placement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_pl_campaign ON meta_insights_engagement_placement(campaign_name);
CREATE INDEX IF NOT EXISTS idx_mie_pl_platform ON meta_insights_engagement_placement(platform);

-- ============================================================
-- 6. S4A — tables globales manquantes
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

CREATE INDEX IF NOT EXISTS idx_s4a_songs_song    ON s4a_songs_global(song);
CREATE INDEX IF NOT EXISTS idx_s4a_songs_streams ON s4a_songs_global(streams DESC);

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

CREATE INDEX IF NOT EXISTS idx_s4a_audience_date   ON s4a_audience(date DESC);
CREATE INDEX IF NOT EXISTS idx_s4a_audience_artist ON s4a_audience(artist_id);

-- Supprimer l'ancienne contrainte s4a_song_timeline(song, date) devenue redondante
-- (remplacée par (artist_id, song, date) pour le support multi-artiste)
ALTER TABLE s4a_song_timeline DROP CONSTRAINT IF EXISTS unique_song_date;

-- ============================================================
-- Confirmation
-- ============================================================
SELECT
    table_name,
    'OK' AS status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'imusician_monthly_revenue',
    'ml_song_predictions',
    'meta_campaigns', 'meta_adsets', 'meta_ads', 'meta_insights',
    'meta_insights_performance', 'meta_insights_performance_day',
    'meta_insights_performance_age', 'meta_insights_performance_country',
    'meta_insights_performance_placement',
    'meta_insights_engagement', 'meta_insights_engagement_day',
    'meta_insights_engagement_age', 'meta_insights_engagement_country',
    'meta_insights_engagement_placement'
  )
ORDER BY table_name;
