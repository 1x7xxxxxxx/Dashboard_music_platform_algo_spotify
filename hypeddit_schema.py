"""Schéma PostgreSQL pour Hypeddit."""

HYPEDDIT_SCHEMA = {
    'hypeddit_campaigns': """
        CREATE TABLE IF NOT EXISTS hypeddit_campaigns (
            campaign_id VARCHAR(50) PRIMARY KEY,
            campaign_name VARCHAR(255) NOT NULL,
            campaign_type VARCHAR(100),
            status VARCHAR(50),
            created_at TIMESTAMP,
            start_date DATE,
            end_date DATE,
            budget DECIMAL(10, 2),
            currency VARCHAR(10) DEFAULT 'USD',
            target_url TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_campaigns_name ON hypeddit_campaigns(campaign_name);
        CREATE INDEX IF NOT EXISTS idx_hypeddit_campaigns_status ON hypeddit_campaigns(status);
        CREATE INDEX IF NOT EXISTS idx_hypeddit_campaigns_dates ON hypeddit_campaigns(start_date, end_date);
    """,
    
    'hypeddit_daily_stats': """
        CREATE TABLE IF NOT EXISTS hypeddit_daily_stats (
            id SERIAL PRIMARY KEY,
            campaign_id VARCHAR(50) NOT NULL REFERENCES hypeddit_campaigns(campaign_id) ON DELETE CASCADE,
            date DATE NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            downloads INTEGER DEFAULT 0,
            streams INTEGER DEFAULT 0,
            follows INTEGER DEFAULT 0,
            pre_saves INTEGER DEFAULT 0,
            spend DECIMAL(10, 2) DEFAULT 0,
            ctr DECIMAL(10, 4) DEFAULT 0,
            conversion_rate DECIMAL(10, 4) DEFAULT 0,
            cost_per_conversion DECIMAL(10, 4) DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_id, date)
        );
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_stats_campaign ON hypeddit_daily_stats(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_hypeddit_stats_date ON hypeddit_daily_stats(date DESC);
        CREATE INDEX IF NOT EXISTS idx_hypeddit_stats_campaign_date ON hypeddit_daily_stats(campaign_id, date);
    """,
    
    'hypeddit_track_mapping': """
        CREATE TABLE IF NOT EXISTS hypeddit_track_mapping (
            id SERIAL PRIMARY KEY,
            campaign_id VARCHAR(50) NOT NULL REFERENCES hypeddit_campaigns(campaign_id) ON DELETE CASCADE,
            track_id VARCHAR(50),
            song_name VARCHAR(255) NOT NULL,
            artist_name VARCHAR(255),
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_id, song_name)
        );
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_mapping_campaign ON hypeddit_track_mapping(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_hypeddit_mapping_track ON hypeddit_track_mapping(track_id);
        CREATE INDEX IF NOT EXISTS idx_hypeddit_mapping_active ON hypeddit_track_mapping(is_active) WHERE is_active = true;
        
        -- Fonction pour mettre à jour updated_at automatiquement
        CREATE OR REPLACE FUNCTION update_hypeddit_mapping_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Trigger pour updated_at
        DROP TRIGGER IF EXISTS trg_hypeddit_mapping_updated_at ON hypeddit_track_mapping;
        CREATE TRIGGER trg_hypeddit_mapping_updated_at
        BEFORE UPDATE ON hypeddit_track_mapping
        FOR EACH ROW
        EXECUTE FUNCTION update_hypeddit_mapping_updated_at();
    """
}


def get_create_table_sql(table_name: str) -> str:
    """Retourne le SQL de création pour une table."""
    return HYPEDDIT_SCHEMA.get(table_name, "")


def get_all_tables() -> list:
    """Retourne la liste de toutes les tables Hypeddit."""
    return list(HYPEDDIT_SCHEMA.keys())


def create_hypeddit_tables():
    """Crée toutes les tables Hypeddit dans PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader
    
    print("\n" + "="*70)
    print("🔧 CRÉATION DES TABLES HYPEDDIT")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db_config = config['database']
    
    db = PostgresHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )
    
    for table_name, sql in HYPEDDIT_SCHEMA.items():
        try:
            print(f"📋 Création table: {table_name}...")
            db.execute_query(sql)
            
            # Vérifier que la table existe
            if db.table_exists(table_name):
                count = db.get_table_count(table_name)
                print(f"   ✅ Table créée ({count} enregistrement(s))")
            else:
                print(f"   ❌ Erreur: table non créée")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
    
    db.close()
    
    print("\n" + "="*70)
    print("✅ TABLES HYPEDDIT CRÉÉES")
    print("="*70 + "\n")


if __name__ == "__main__":
    create_hypeddit_tables()