"""Schéma PostgreSQL pour Hypeddit (saisie manuelle)."""

HYPEDDIT_MANUAL_SCHEMA = {
    'hypeddit_campaigns_manual': """
        CREATE TABLE IF NOT EXISTS hypeddit_campaigns_manual (
            id SERIAL PRIMARY KEY,
            campaign_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT true,
            UNIQUE(campaign_name)
        );
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_manual_campaigns_name 
        ON hypeddit_campaigns_manual(campaign_name);
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_manual_campaigns_active 
        ON hypeddit_campaigns_manual(is_active) WHERE is_active = true;
    """,
    
    'hypeddit_daily_stats_manual': """
        CREATE TABLE IF NOT EXISTS hypeddit_daily_stats_manual (
            id SERIAL PRIMARY KEY,
            campaign_name VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            visits INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            budget DECIMAL(10, 2) DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            ctr DECIMAL(10, 4) DEFAULT 0,
            cost_per_click DECIMAL(10, 4) DEFAULT 0,
            cost_per_conversion DECIMAL(10, 4) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_name, date)
        );
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_manual_stats_campaign 
        ON hypeddit_daily_stats_manual(campaign_name);
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_manual_stats_date 
        ON hypeddit_daily_stats_manual(date DESC);
        
        CREATE INDEX IF NOT EXISTS idx_hypeddit_manual_stats_campaign_date 
        ON hypeddit_daily_stats_manual(campaign_name, date);
        
        -- Fonction pour calculer automatiquement les métriques
        CREATE OR REPLACE FUNCTION calculate_hypeddit_metrics()
        RETURNS TRIGGER AS $$
        BEGIN
            -- CTR (Click-Through Rate)
            IF NEW.visits > 0 THEN
                NEW.ctr = ROUND((NEW.clicks::numeric / NEW.visits::numeric) * 100, 4);
            ELSE
                NEW.ctr = 0;
            END IF;
            
            -- Cost per Click
            IF NEW.clicks > 0 THEN
                NEW.cost_per_click = ROUND(NEW.budget / NEW.clicks, 4);
            ELSE
                NEW.cost_per_click = NULL;
            END IF;
            
            -- Cost per Conversion
            IF NEW.conversions > 0 THEN
                NEW.cost_per_conversion = ROUND(NEW.budget / NEW.conversions, 4);
            ELSE
                NEW.cost_per_conversion = NULL;
            END IF;
            
            -- Mise à jour du timestamp
            NEW.updated_at = CURRENT_TIMESTAMP;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Trigger pour calcul automatique
        DROP TRIGGER IF EXISTS trg_calculate_hypeddit_metrics ON hypeddit_daily_stats_manual;
        CREATE TRIGGER trg_calculate_hypeddit_metrics
        BEFORE INSERT OR UPDATE ON hypeddit_daily_stats_manual
        FOR EACH ROW
        EXECUTE FUNCTION calculate_hypeddit_metrics();
    """
}


def create_hypeddit_manual_tables():
    """Crée les tables Hypeddit pour saisie manuelle."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader
    
    print("\n" + "="*70)
    print("🔧 CRÉATION TABLES HYPEDDIT (SAISIE MANUELLE)")
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
    
    for table_name, sql in HYPEDDIT_MANUAL_SCHEMA.items():
        try:
            print(f"📋 Création table: {table_name}...")
            db.execute_query(sql)
            
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
    create_hypeddit_manual_tables()