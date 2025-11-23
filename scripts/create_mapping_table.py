import sys
import os
from pathlib import Path

# On remonte de 2 niveaux (scripts -> racine du projet) pour trouver 'src'
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Maintenant les imports fonctionneront
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

def create_mapping_table():
    """Crée la table meta_spotify_mapping."""
    print("\n" + "="*70)
    print("🔗 CRÉATION TABLE DE MAPPING META x SPOTIFY")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # Schéma de la table
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS meta_spotify_mapping (
            id SERIAL PRIMARY KEY,
            campaign_id VARCHAR(50) NOT NULL,
            song VARCHAR(255) NOT NULL,
            track_id VARCHAR(50),
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_id, song)
        );
        
        -- Index pour optimiser les jointures
        CREATE INDEX IF NOT EXISTS idx_mapping_campaign 
        ON meta_spotify_mapping(campaign_id);
        
        CREATE INDEX IF NOT EXISTS idx_mapping_song 
        ON meta_spotify_mapping(song);
        
        CREATE INDEX IF NOT EXISTS idx_mapping_track 
        ON meta_spotify_mapping(track_id);
        
        CREATE INDEX IF NOT EXISTS idx_mapping_active 
        ON meta_spotify_mapping(is_active) WHERE is_active = true;
        
        -- Clé étrangère vers meta_campaigns
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'meta_spotify_mapping_campaign_fkey'
            ) THEN
                ALTER TABLE meta_spotify_mapping
                ADD CONSTRAINT meta_spotify_mapping_campaign_fkey
                FOREIGN KEY (campaign_id) REFERENCES meta_campaigns(campaign_id)
                ON DELETE CASCADE;
            END IF;
        END $$;
        
        -- Fonction pour mettre à jour updated_at automatiquement
        CREATE OR REPLACE FUNCTION update_mapping_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Trigger pour updated_at
        DROP TRIGGER IF EXISTS trg_mapping_updated_at ON meta_spotify_mapping;
        CREATE TRIGGER trg_mapping_updated_at
        BEFORE UPDATE ON meta_spotify_mapping
        FOR EACH ROW
        EXECUTE FUNCTION update_mapping_updated_at();
    """
    
    try:
        print("🔄 Création de la table meta_spotify_mapping...")
        db.execute_query(create_table_sql)
        print("   ✅ Table créée avec succès")
        
        # Vérifier la structure
        verify_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'meta_spotify_mapping'
            ORDER BY ordinal_position;
        """
        
        df_structure = db.fetch_df(verify_query)
        
        print("\n📋 Structure de la table :")
        print("-" * 70)
        print(df_structure.to_string(index=False))
        
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
    
    print("\n" + "="*70)
    print("✅ TABLE DE MAPPING CRÉÉE")
    print("="*70 + "\n")
    
    db.close()

if __name__ == "__main__":
    create_mapping_table()