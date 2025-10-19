"""Script de vérification des données Meta Ads dans PostgreSQL."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader
from datetime import datetime, timedelta


def verify_meta_ads_data():
    """Vérifie l'intégrité des données Meta Ads."""
    print("\n" + "="*70)
    print("🔍 VÉRIFICATION DES DONNÉES META ADS")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # 1. Compter les enregistrements
    print("📊 NOMBRE D'ENREGISTREMENTS")
    print("-" * 70)
    
    tables = ['meta_campaigns', 'meta_adsets', 'meta_ads', 'meta_insights']
    for table in tables:
        count = db.get_table_count(table)
        print(f"   • {table:20s} : {count:>6,} lignes")
    
    print()
    
    # 2. Vérifier les campagnes
    print("🎯 CAMPAGNES")
    print("-" * 70)
    
    campaigns_query = """
        SELECT 
            campaign_id,
            campaign_name,
            status,
            objective,
            daily_budget,
            lifetime_budget
        FROM meta_campaigns
        ORDER BY campaign_name
    """
    
    campaigns_df = db.fetch_df(campaigns_query)
    
    if not campaigns_df.empty:
        print(f"   Total: {len(campaigns_df)} campagnes\n")
        
        # Afficher uniquement les 10 premières
        display_df = campaigns_df.head(10)
        print(display_df.to_string(index=False, max_colwidth=40))
        
        if len(campaigns_df) > 10:
            print(f"\n   ... et {len(campaigns_df) - 10} autres campagnes")
    else:
        print("   ⚠️ Aucune campagne trouvée")
    
    print("\n")
    
    # 3. Statistiques par statut
    print("📈 RÉPARTITION PAR STATUT")
    print("-" * 70)
    
    # Campagnes
    if not campaigns_df.empty:
        print("   Campagnes :")
        status_counts = campaigns_df['status'].value_counts()
        for status, count in status_counts.items():
            print(f"      • {status:15s} : {count:>6,}")
    
    # Ads
    ads_status_query = """
        SELECT status, COUNT(*) as count
        FROM meta_ads
        GROUP BY status
        ORDER BY count DESC
    """
    
    status_df = db.fetch_df(ads_status_query)
    
    if not status_df.empty:
        print("\n   Ads :")
        for _, row in status_df.iterrows():
            print(f"      • {row['status']:15s} : {row['count']:>6,}")
    
    print("\n")
    
    # 4. Insights des 7 derniers jours
    print("📊 INSIGHTS (7 derniers jours)")
    print("-" * 70)
    
    insights_query = """
        SELECT 
            date,
            COUNT(DISTINCT ad_id) as num_ads,
            SUM(impressions) as total_impressions,
            SUM(clicks) as total_clicks,
            SUM(spend) as total_spend,
            SUM(conversions) as total_conversions,
            ROUND(AVG(ctr), 2) as avg_ctr
        FROM meta_insights
        WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY date
        ORDER BY date DESC
    """
    
    insights_df = db.fetch_df(insights_query)
    
    if not insights_df.empty:
        print(insights_df.to_string(index=False))
        
        # Totaux
        print("\n   📊 TOTAUX (7 jours):")
        print(f"      • Impressions  : {insights_df['total_impressions'].sum():>12,}")
        print(f"      • Clicks       : {insights_df['total_clicks'].sum():>12,}")
        print(f"      • Spend        : {insights_df['total_spend'].sum():>12,.2f} €")
        print(f"      • Conversions  : {insights_df['total_conversions'].sum():>12,}")
    else:
        print("   ⚠️ Aucun insight récent trouvé")
    
    print("\n")
    
    # 5. Top 10 ads par performance
    print("🏆 TOP 10 ADS (par impressions - 30 derniers jours)")
    print("-" * 70)
    
    top_ads_query = """
        SELECT 
            a.ad_name,
            c.campaign_name,
            SUM(i.impressions) as total_impressions,
            SUM(i.clicks) as total_clicks,
            SUM(i.spend) as total_spend,
            SUM(i.conversions) as total_conversions,
            ROUND(AVG(i.ctr), 2) as avg_ctr
        FROM meta_insights i
        JOIN meta_ads a ON i.ad_id = a.ad_id
        JOIN meta_campaigns c ON a.campaign_id = c.campaign_id
        WHERE i.date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY a.ad_name, c.campaign_name
        ORDER BY total_impressions DESC
        LIMIT 10
    """
    
    top_ads_df = db.fetch_df(top_ads_query)
    
    if not top_ads_df.empty:
        print(top_ads_df.to_string(index=False, max_colwidth=40))
    else:
        print("   ⚠️ Aucune donnée disponible")
    
    print("\n")
    
    # 6. Dernière collecte
    print("🕐 DERNIÈRE COLLECTE")
    print("-" * 70)
    
    last_collect_query = """
        SELECT 
            MAX(collected_at) as last_collection,
            'campaigns' as source
        FROM meta_campaigns
        UNION ALL
        SELECT 
            MAX(collected_at) as last_collection,
            'insights' as source
        FROM meta_insights
        ORDER BY last_collection DESC
    """
    
    last_collect_df = db.fetch_df(last_collect_query)
    
    if not last_collect_df.empty:
        for _, row in last_collect_df.iterrows():
            if row['last_collection']:
                delta = datetime.now() - row['last_collection']
                status = "✅ Récent" if delta < timedelta(days=1) else "⚠️ Ancien"
                
                print(f"   {row['source']:15s} : {row['last_collection']} ({status})")
    else:
        print("   ❌ Aucune collecte enregistrée")
    
    print("\n" + "="*70)
    print("✅ VÉRIFICATION TERMINÉE")
    print("="*70 + "\n")
    
    db.close()


if __name__ == "__main__":
    verify_meta_ads_data()