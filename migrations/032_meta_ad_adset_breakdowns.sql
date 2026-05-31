-- 032 — Meta Ads breakdowns (country / placement / age) at AD and ADSET grain.
--
-- The campaign-level breakdowns (meta_insights_performance_country, etc.) already
-- exist. These 12 tables add the same dimensions at ad (= creative) and adset grain,
-- for BOTH performance and engagement, powering the multi-grain "Breakdowns Meta" view.
-- Keyed by ad_id / adset_id (FK to meta_ads / meta_adsets, both VARCHAR(50) PKs).
-- Aggregate over the full retention window (no date dimension) — same as the campaign
-- breakdowns. Populated by MetaAdsApiCollector._fetch_breakdown on the next full run.

-- ── Performance — AD level ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meta_insights_performance_ad_country (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_id VARCHAR(50) NOT NULL REFERENCES meta_ads(ad_id),
    country VARCHAR(100) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0, impressions INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0, custom_conversions INTEGER DEFAULT 0, cpr DECIMAL(10, 4),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, ad_id, country)
);
CREATE INDEX IF NOT EXISTS idx_mip_adctry_artist ON meta_insights_performance_ad_country(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_adctry_ad     ON meta_insights_performance_ad_country(ad_id);

CREATE TABLE IF NOT EXISTS meta_insights_performance_ad_placement (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_id VARCHAR(50) NOT NULL REFERENCES meta_ads(ad_id),
    platform VARCHAR(100) NOT NULL, placement VARCHAR(100) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0, impressions INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0, custom_conversions INTEGER DEFAULT 0, cpr DECIMAL(10, 4),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, ad_id, platform, placement)
);
CREATE INDEX IF NOT EXISTS idx_mip_adplc_artist ON meta_insights_performance_ad_placement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_adplc_ad     ON meta_insights_performance_ad_placement(ad_id);

CREATE TABLE IF NOT EXISTS meta_insights_performance_ad_age (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_id VARCHAR(50) NOT NULL REFERENCES meta_ads(ad_id),
    age_range VARCHAR(50) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0, impressions INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0, custom_conversions INTEGER DEFAULT 0, cpr DECIMAL(10, 4),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, ad_id, age_range)
);
CREATE INDEX IF NOT EXISTS idx_mip_adage_artist ON meta_insights_performance_ad_age(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_adage_ad     ON meta_insights_performance_ad_age(ad_id);

-- ── Performance — ADSET level ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meta_insights_performance_adset_country (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    adset_id VARCHAR(50) NOT NULL REFERENCES meta_adsets(adset_id),
    country VARCHAR(100) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0, impressions INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0, custom_conversions INTEGER DEFAULT 0, cpr DECIMAL(10, 4),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, adset_id, country)
);
CREATE INDEX IF NOT EXISTS idx_mip_asctry_artist ON meta_insights_performance_adset_country(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_asctry_adset  ON meta_insights_performance_adset_country(adset_id);

CREATE TABLE IF NOT EXISTS meta_insights_performance_adset_placement (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    adset_id VARCHAR(50) NOT NULL REFERENCES meta_adsets(adset_id),
    platform VARCHAR(100) NOT NULL, placement VARCHAR(100) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0, impressions INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0, custom_conversions INTEGER DEFAULT 0, cpr DECIMAL(10, 4),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, adset_id, platform, placement)
);
CREATE INDEX IF NOT EXISTS idx_mip_asplc_artist ON meta_insights_performance_adset_placement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_asplc_adset  ON meta_insights_performance_adset_placement(adset_id);

CREATE TABLE IF NOT EXISTS meta_insights_performance_adset_age (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    adset_id VARCHAR(50) NOT NULL REFERENCES meta_adsets(adset_id),
    age_range VARCHAR(50) NOT NULL,
    spend DECIMAL(10, 4) DEFAULT 0, impressions INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
    results INTEGER DEFAULT 0, custom_conversions INTEGER DEFAULT 0, cpr DECIMAL(10, 4),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, adset_id, age_range)
);
CREATE INDEX IF NOT EXISTS idx_mip_asage_artist ON meta_insights_performance_adset_age(artist_id);
CREATE INDEX IF NOT EXISTS idx_mip_asage_adset  ON meta_insights_performance_adset_age(adset_id);

-- ── Engagement — AD level ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meta_insights_engagement_ad_country (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_id VARCHAR(50) NOT NULL REFERENCES meta_ads(ad_id),
    country VARCHAR(100) NOT NULL,
    page_interactions INTEGER DEFAULT 0, post_reactions INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0, shares INTEGER DEFAULT 0, link_clicks INTEGER DEFAULT 0, post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, ad_id, country)
);
CREATE INDEX IF NOT EXISTS idx_mie_adctry_artist ON meta_insights_engagement_ad_country(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_adctry_ad     ON meta_insights_engagement_ad_country(ad_id);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_ad_placement (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_id VARCHAR(50) NOT NULL REFERENCES meta_ads(ad_id),
    platform VARCHAR(100) NOT NULL, placement VARCHAR(100) NOT NULL,
    page_interactions INTEGER DEFAULT 0, post_reactions INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0, shares INTEGER DEFAULT 0, link_clicks INTEGER DEFAULT 0, post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, ad_id, platform, placement)
);
CREATE INDEX IF NOT EXISTS idx_mie_adplc_artist ON meta_insights_engagement_ad_placement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_adplc_ad     ON meta_insights_engagement_ad_placement(ad_id);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_ad_age (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    ad_id VARCHAR(50) NOT NULL REFERENCES meta_ads(ad_id),
    age_range VARCHAR(50) NOT NULL,
    page_interactions INTEGER DEFAULT 0, post_reactions INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0, shares INTEGER DEFAULT 0, link_clicks INTEGER DEFAULT 0, post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, ad_id, age_range)
);
CREATE INDEX IF NOT EXISTS idx_mie_adage_artist ON meta_insights_engagement_ad_age(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_adage_ad     ON meta_insights_engagement_ad_age(ad_id);

-- ── Engagement — ADSET level ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meta_insights_engagement_adset_country (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    adset_id VARCHAR(50) NOT NULL REFERENCES meta_adsets(adset_id),
    country VARCHAR(100) NOT NULL,
    page_interactions INTEGER DEFAULT 0, post_reactions INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0, shares INTEGER DEFAULT 0, link_clicks INTEGER DEFAULT 0, post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, adset_id, country)
);
CREATE INDEX IF NOT EXISTS idx_mie_asctry_artist ON meta_insights_engagement_adset_country(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_asctry_adset  ON meta_insights_engagement_adset_country(adset_id);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_adset_placement (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    adset_id VARCHAR(50) NOT NULL REFERENCES meta_adsets(adset_id),
    platform VARCHAR(100) NOT NULL, placement VARCHAR(100) NOT NULL,
    page_interactions INTEGER DEFAULT 0, post_reactions INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0, shares INTEGER DEFAULT 0, link_clicks INTEGER DEFAULT 0, post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, adset_id, platform, placement)
);
CREATE INDEX IF NOT EXISTS idx_mie_asplc_artist ON meta_insights_engagement_adset_placement(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_asplc_adset  ON meta_insights_engagement_adset_placement(adset_id);

CREATE TABLE IF NOT EXISTS meta_insights_engagement_adset_age (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    adset_id VARCHAR(50) NOT NULL REFERENCES meta_adsets(adset_id),
    age_range VARCHAR(50) NOT NULL,
    page_interactions INTEGER DEFAULT 0, post_reactions INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0, shares INTEGER DEFAULT 0, link_clicks INTEGER DEFAULT 0, post_likes INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, adset_id, age_range)
);
CREATE INDEX IF NOT EXISTS idx_mie_asage_artist ON meta_insights_engagement_adset_age(artist_id);
CREATE INDEX IF NOT EXISTS idx_mie_asage_adset  ON meta_insights_engagement_adset_age(adset_id);
