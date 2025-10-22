"""Vérification du schéma Meta Ads."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

def check_schema():
    """Vérifie la structure des tables Meta Ads."""
    print("\n" + "="*70)
    print("🔍 VÉRIFICATION SCHÉMA META ADS")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # 1. Vérifier la structure de meta_insights
    print("📊 Structure de la table 'meta_insights' :")
    print("-" * 70)
    
    columns_query = """
        SELECT 
            column_name, 
            data_type, 
            is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'meta_insights'
        ORDER BY ordinal_position;
    """
    
    df_columns = db.fetch_df(columns_query)
    
    if not df_columns.empty:
        print(df_columns.to_string(index=False))
        
        # Vérifier si cost_per_conversion existe
        if 'cost_per_conversion' in df_columns['column_name'].values:
            print("\n✅ Colonne 'cost_per_conversion' existe")
        else:
            print("\n❌ Colonne 'cost_per_conversion' MANQUANTE")
    else:
        print("❌ Table 'meta_insights' introuvable")
    
    print("\n" + "="*70)
    
    # 2. Vérifier les index existants
    print("\n📑 Index existants sur les tables Meta Ads :")
    print("-" * 70)
    
    indexes_query = """
        SELECT 
            tablename,
            indexname,
            indexdef
        FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND tablename LIKE 'meta_%'
        ORDER BY tablename, indexname;
    """
    
    df_indexes = db.fetch_df(indexes_query)
    
    if not df_indexes.empty:
        for table in df_indexes['tablename'].unique():
            print(f"\n📋 Table: {table}")
            table_indexes = df_indexes[df_indexes['tablename'] == table]
            for _, idx in table_indexes.iterrows():
                print(f"   • {idx['indexname']}")
    else:
        print("⚠️ Aucun index trouvé")
    
    print("\n" + "="*70)
    
    # 3. Compter les enregistrements
    print("\n📊 Nombre d'enregistrements :")
    print("-" * 70)
    
    tables = ['meta_campaigns', 'meta_adsets', 'meta_ads', 'meta_insights']
    for table in tables:
        try:
            count = db.get_table_count(table)
            print(f"   • {table:20s} : {count:>6,} lignes")
        except:
            print(f"   • {table:20s} : ❌ Table introuvable")
    
    print("\n" + "="*70)
    print("✅ VÉRIFICATION TERMINÉE")
    print("="*70 + "\n")
    
    db.close()

if __name__ == "__main__":
    check_schema()