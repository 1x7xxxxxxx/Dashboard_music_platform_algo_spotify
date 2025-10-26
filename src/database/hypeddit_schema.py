"""Schéma PostgreSQL pour Hypeddit (saisie manuelle)."""

HYPEDDIT_SCHEMA = {
    'hypeddit_campaigns': """
        -- Supprimer la table existante si elle existe
        DROP TABLE IF EXISTS hypeddit_daily_stats CASCADE;
        DROP TABLE IF EXISTS hypeddit_campaigns CASCADE;
        
        -- Créer la table des campagnes
        CREATE TABLE hypeddit_campaigns (
            id SERIAL PRIMARY KEY,
            campaign_name VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT true
        );
        
        CREATE INDEX idx_hypeddit_campaigns_name 
        ON hypeddit_campaigns(campaign_name);
        
        CREATE INDEX idx_hypeddit_campaigns_active 
        ON hypeddit_campaigns(is_active) WHERE is_active = true;
    """,
    
    'hypeddit_daily_stats': """
        -- Créer la table des statistiques quotidiennes
        CREATE TABLE hypeddit_daily_stats (
            id SERIAL PRIMARY KEY,
            campaign_name VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            visits INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            budget DECIMAL(10, 2) DEFAULT 0,
            ctr DECIMAL(10, 4) DEFAULT 0,
            cost_per_click DECIMAL(10, 4) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_name, date),
            CONSTRAINT fk_hypeddit_campaign 
                FOREIGN KEY (campaign_name) 
                REFERENCES hypeddit_campaigns(campaign_name)
                ON DELETE CASCADE
        );
        
        CREATE INDEX idx_hypeddit_stats_campaign 
        ON hypeddit_daily_stats(campaign_name);
        
        CREATE INDEX idx_hypeddit_stats_date 
        ON hypeddit_daily_stats(date DESC);
        
        CREATE INDEX idx_hypeddit_stats_campaign_date 
        ON hypeddit_daily_stats(campaign_name, date);
        
        -- Fonction pour calculer automatiquement CTR et CPC
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
            
            NEW.updated_at = CURRENT_TIMESTAMP;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Trigger pour calcul automatique
        DROP TRIGGER IF EXISTS trg_calculate_hypeddit_metrics ON hypeddit_daily_stats;
        CREATE TRIGGER trg_calculate_hypeddit_metrics
        BEFORE INSERT OR UPDATE ON hypeddit_daily_stats
        FOR EACH ROW
        EXECUTE FUNCTION calculate_hypeddit_metrics();
    """
}


def create_hypeddit_tables():
    """Crée les tables Hypeddit."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader
    
    print("\n" + "="*70)
    print("🔧 CRÉATION TABLES HYPEDDIT")
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
    
    try:
        # Exécuter dans l'ordre : campaigns puis stats
        print("📋 Suppression et création de hypeddit_campaigns...")
        db.execute_query(HYPEDDIT_SCHEMA['hypeddit_campaigns'])
        print("   ✅ Table hypeddit_campaigns créée")
        
        print("📋 Création de hypeddit_daily_stats...")
        db.execute_query(HYPEDDIT_SCHEMA['hypeddit_daily_stats'])
        print("   ✅ Table hypeddit_daily_stats créée")
        
        # Vérifier la structure
        print("\n🔍 Vérification de la structure...")
        
        campaigns_count = db.get_table_count('hypeddit_campaigns')
        stats_count = db.get_table_count('hypeddit_daily_stats')
        
        print(f"   ✅ hypeddit_campaigns: {campaigns_count} enregistrement(s)")
        print(f"   ✅ hypeddit_daily_stats: {stats_count} enregistrement(s)")
        
        # Afficher la structure de la table campaigns
        verify_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'hypeddit_campaigns'
            ORDER BY ordinal_position;
        """
        
        df_structure = db.fetch_df(verify_query)
        
        print("\n📋 Structure de hypeddit_campaigns :")
        print("-" * 70)
        print(df_structure.to_string(index=False))
        
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
    
    db.close()
    
    print("\n" + "="*70)
    print("✅ TABLES HYPEDDIT CRÉÉES")
    print("="*70 + "\n")


if __name__ == "__main__":
    create_hypeddit_tables()