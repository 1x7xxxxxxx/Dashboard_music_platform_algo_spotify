"""
Script d'ingestion complet pour Meta Ads (Historique) avec découpage mensuel et gestion des orphelins.
"""
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

# Setup des chemins
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

load_dotenv(project_root / '.env')

from src.collectors.meta_ads_collector import MetaAdsCollector
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_full_ingestion():
    print("\n" + "="*70)
    print("🚀 INGESTION COMPLÈTE META ADS (Mode Chunking + Anti-Orphelins)")
    print("="*70)

    # 1. Config & Connexion
    try:
        app_id = os.getenv('META_APP_ID')
        access_token = os.getenv('META_ACCESS_TOKEN')
        ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        app_secret = os.getenv('META_APP_SECRET')
        
        try:
            config = config_loader.load()
            db_config = config['database']
        except:
            db_config = {
                'host': os.getenv('DATABASE_HOST', 'localhost'),
                'port': int(os.getenv('DATABASE_PORT', 5433)),
                'database': os.getenv('DATABASE_NAME', 'spotify_etl'),
                'user': os.getenv('DATABASE_USER', 'postgres'),
                'password': os.getenv('DATABASE_PASSWORD')
            }

        collector = MetaAdsCollector(app_id, app_secret, access_token, ad_account_id)
        db = PostgresHandler(**db_config)
        print("✅ Connexions initialisées.")

    except Exception as e:
        print(f"❌ Erreur Config: {e}")
        return

    try:
        # --- 1. CAMPAGNES ---
        print("\n📊 1/4 Récupération Campagnes...")
        campaigns = collector.get_campaigns()
        valid_campaign_ids = set()
        
        if campaigns:
            db.upsert_many('meta_campaigns', campaigns, ['campaign_id'], 
                          ['campaign_name', 'status', 'objective', 'daily_budget', 'lifetime_budget', 'start_time', 'end_time', 'created_time'])
            valid_campaign_ids = {c['campaign_id'] for c in campaigns}
            print(f"   ✅ {len(campaigns)} campagnes sauvegardées.")
        else:
            print("   ⚠️ Aucune campagne trouvée.")

        # --- 2. ADSETS (Ensembles de pubs) ---
        print("\n📂 2/4 Récupération AdSets...")
        adsets = collector.get_adsets()
        valid_adset_ids = set()
        
        if adsets:
            # FILTRAGE : On ne garde que les AdSets dont la campagne parente existe
            clean_adsets = [a for a in adsets if a['campaign_id'] in valid_campaign_ids]
            
            # OPTION : Si vous voulez forcer l'insertion même des orphelins (décommentez la ligne ci-dessous)
            # clean_adsets = adsets 
            
            orphans = len(adsets) - len(clean_adsets)
            
            if clean_adsets:
                db.upsert_many('meta_adsets', clean_adsets, ['adset_id'], 
                              ['adset_name', 'campaign_id', 'status', 'daily_budget', 'start_time', 'end_time', 'targeting'])
                valid_adset_ids = {a['adset_id'] for a in clean_adsets}
                print(f"   ✅ {len(clean_adsets)} adsets sauvegardés.")
            
            if orphans > 0:
                print(f"   🗑️ {orphans} adsets orphelins ignorés (campagne parente introuvable).")

        # --- 3. ADS (Publicités) ---
        print("\n📢 3/4 Récupération Ads...")
        ads = collector.get_ads()
        valid_ad_ids = set()
        
        if ads:
            # FILTRAGE : On ne garde que les Ads dont l'AdSet parent existe
            clean_ads = [a for a in ads if a['adset_id'] in valid_adset_ids]
            
            # OPTION : Si vous voulez forcer l'insertion même des orphelins (décommentez la ligne ci-dessous)
            # clean_ads = ads
            
            orphans = len(ads) - len(clean_ads)
            
            if clean_ads:
                db.upsert_many('meta_ads', clean_ads, ['ad_id'], 
                              ['ad_name', 'adset_id', 'campaign_id', 'status', 'creative_id', 'created_time'])
                valid_ad_ids = {a['ad_id'] for a in clean_ads}
                print(f"   ✅ {len(clean_ads)} publicités sauvegardées.")
            
            if orphans > 0:
                print(f"   🗑️ {orphans} publicités orphelines ignorées (adset parent introuvable).")

        # --- 4. INSIGHTS (Boucle Mensuelle) ---
        print(f"\n📈 4/4 Récupération Insights (Mode Mensuel)...")
        
        current_date = datetime(2023, 1, 1)
        end_date = datetime.now()
        
        total_insights = 0
        
        while current_date <= end_date:
            next_month = current_date + relativedelta(months=1)
            period_end = min(next_month - timedelta(days=1), end_date)
            
            date_range = {
                'since': current_date.strftime('%Y-%m-%d'),
                'until': period_end.strftime('%Y-%m-%d')
            }
            
            print(f"   ⏳ Traitement période : {date_range['since']} -> {date_range['until']}")
            
            try:
                # Hack pour appeler l'API avec time_range personnalisé
                from facebook_business.adobjects.adsinsights import AdsInsights
                
                params = {
                    'level': 'ad',
                    'time_range': date_range,
                    'time_increment': 1,
                    'limit': 5000
                }
                
                fields = [
                    AdsInsights.Field.campaign_id, AdsInsights.Field.adset_id, AdsInsights.Field.ad_id,
                    AdsInsights.Field.date_start, AdsInsights.Field.impressions, AdsInsights.Field.clicks,
                    AdsInsights.Field.spend, AdsInsights.Field.reach, AdsInsights.Field.frequency,
                    AdsInsights.Field.cpc, AdsInsights.Field.cpm, AdsInsights.Field.ctr,
                    AdsInsights.Field.actions, AdsInsights.Field.cost_per_action_type
                ]
                
                insights_iter = collector.ad_account.get_insights(fields=fields, params=params)
                
                batch_data = []
                for insight in insights_iter:
                    actions = insight.get('actions', [])
                    
                    # Logique de conversion stricte (Lien ou Offsite)
                    relevant_action_types = ['link_click', 'offsite_conversion.custom']
                    total_conversions = 0
                    if actions:
                        for action in actions:
                            if action['action_type'] in relevant_action_types:
                                total_conversions += float(action['value'])

                    cost_per_actions = insight.get('cost_per_action_type', [])
                    cost_per_conv = 0.0
                    if cost_per_actions and total_conversions > 0:
                         for cpa in cost_per_actions:
                            if cpa['action_type'] in relevant_action_types:
                                cost_per_conv = float(cpa['value'])
                                break

                    record = {
                        'ad_id': insight['ad_id'],
                        'date': insight['date_start'],
                        'impressions': int(insight.get('impressions', 0)),
                        'clicks': int(insight.get('clicks', 0)),
                        'spend': float(insight.get('spend', 0)),
                        'reach': int(insight.get('reach', 0)),
                        'frequency': float(insight.get('frequency', 0)),
                        'cpc': float(insight.get('cpc', 0)) if 'cpc' in insight else 0.0,
                        'cpm': float(insight.get('cpm', 0)) if 'cpm' in insight else 0.0,
                        'ctr': float(insight.get('ctr', 0)) if 'ctr' in insight else 0.0,
                        'conversions': int(total_conversions),
                        'cost_per_conversion': cost_per_conv,
                        'collected_at': datetime.now()
                    }
                    batch_data.append(record)
                
                # FILTRAGE : On ne garde que les stats des Ads qui existent
                clean_insights = [i for i in batch_data if i['ad_id'] in valid_ad_ids]
                
                # OPTION : Si vous voulez forcer l'insertion même sans parent (décommentez la ligne ci-dessous)
                # clean_insights = batch_data

                orphans = len(batch_data) - len(clean_insights)
                
                if clean_insights:
                    db.upsert_many('meta_insights', clean_insights, ['ad_id', 'date'], 
                                  ['impressions', 'clicks', 'spend', 'ctr', 'cpc', 'conversions', 'cost_per_conversion'])
                    total_insights += len(clean_insights)
                    print(f"      ✅ {len(clean_insights)} lignes insérées.")
                
                if orphans > 0:
                    print(f"      🗑️ {orphans} lignes ignorées (pub introuvable).")

            except Exception as e:
                print(f"      ❌ Erreur sur ce mois : {e}")
            
            current_date = next_month

        print(f"\n✨ Total Historique : {total_insights} lignes d'insights récupérées.")

    except Exception as e:
        print(f"❌ Erreur critique : {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()
        print("\n🏁 Terminé.")

if __name__ == "__main__":
    run_full_ingestion()