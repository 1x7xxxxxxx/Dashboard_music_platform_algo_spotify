"""Schéma PostgreSQL pour Meta Ads."""

META_ADS_SCHEMA = {
    'meta_campaigns': """
        CREATE TABLE IF NOT EXISTS meta_campaigns (
            campaign_id VARCHAR(50) PRIMARY KEY,
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
        
        CREATE INDEX IF NOT EXISTS idx_meta_campaigns_name ON meta_campaigns(campaign_name);
        CREATE INDEX IF NOT EXISTS idx_meta_campaigns_status ON meta_campaigns(status);
    """,
    
    'meta_adsets': """
        CREATE TABLE IF NOT EXISTS meta_adsets (
            adset_id VARCHAR(50) PRIMARY KEY,
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
    """,
    
    'meta_ads': """
        CREATE TABLE IF NOT EXISTS meta_ads (
            ad_id VARCHAR(50) PRIMARY KEY,
            ad_name VARCHAR(255) NOT NULL,
            adset_id VARCHAR(50) REFERENCES meta_adsets(adset_id),
            campaign_id VARCHAR(50) REFERENCES meta_campaigns(campaign_id),
            status VARCHAR(50),
            creative_id VARCHAR(50),
            created_time TIMESTAMP,
            updated_time TIMESTAMP,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_meta_ads_adset ON meta_ads(adset_id);
        CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign ON meta_ads(campaign_id);
    """,
    
    'meta_insights': """
        CREATE TABLE IF NOT EXISTS meta_insights (
            id SERIAL PRIMARY KEY,
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
        
        CREATE INDEX IF NOT EXISTS idx_meta_insights_ad ON meta_insights(ad_id);
        CREATE INDEX IF NOT EXISTS idx_meta_insights_date ON meta_insights(date DESC);
        CREATE INDEX IF NOT EXISTS idx_meta_insights_ad_date ON meta_insights(ad_id, date);
    """
}


def get_create_table_sql(table_name: str) -> str:
    """Retourne le SQL de création pour une table."""
    return META_ADS_SCHEMA.get(table_name, "")


def get_all_tables() -> list:
    """Retourne la liste de toutes les tables Meta Ads."""
    return list(META_ADS_SCHEMA.keys())