"""Schéma PostgreSQL pour les tables Meta Ads Insights (CSV watcher).

10 tables réparties en deux familles :
  - Performance (spend, impressions, reach, cpc, ctr…)
  - Engagement  (reactions, comments, saves, shares…)

Chaque famille est déclinée en 5 granularités : global, day, age, country, placement.
"""

META_INSIGHT_SCHEMA = {

    # ── Performance ──────────────────────────────────────────────────────────

    'meta_insights_performance': """
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
    """,

    'meta_insights_performance_day': """
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
    """,

    'meta_insights_performance_age': """
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
    """,

    'meta_insights_performance_country': """
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
    """,

    'meta_insights_performance_placement': """
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
    """,

    # ── Engagement ───────────────────────────────────────────────────────────

    'meta_insights_engagement': """
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
    """,

    'meta_insights_engagement_day': """
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
    """,

    'meta_insights_engagement_age': """
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
    """,

    'meta_insights_engagement_country': """
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
    """,

    'meta_insights_engagement_placement': """
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
    """,
}


def get_create_table_sql(table_name: str) -> str:
    """Retourne le SQL de création pour une table."""
    return META_INSIGHT_SCHEMA.get(table_name, "")


def get_all_tables() -> list:
    """Retourne la liste de toutes les tables Meta Insights."""
    return list(META_INSIGHT_SCHEMA.keys())
