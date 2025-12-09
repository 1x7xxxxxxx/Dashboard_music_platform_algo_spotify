"""Collector pour Meta Ads API - FILTRAGE STRICT (ACTIVE/PAUSED)."""
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from functools import wraps
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adsinsights import AdsInsights

logger = logging.getLogger(__name__)

def retry_on_rate_limit(max_retries=3, delay=60):
    """Décorateur pour gérer les rate limits Meta Ads."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e)
                    if any(x in error_str for x in ['rate limit', 'User request limit', 'code": 17', 'code": 4']):
                        if attempt < max_retries - 1:
                            wait_time = delay * (attempt + 1)
                            logger.warning(f"⏳ Rate limit atteint (tentative {attempt + 1}/{max_retries}). Attente de {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                    raise e
            return func(*args, **kwargs)
        return wrapper
    return decorator

class MetaAdsCollector:
    """Classe pour interagir avec l'API Meta Marketing."""

    def __init__(self, app_id: str, app_secret: str, access_token: str, ad_account_id: str, api_version: str = 'v21.0'):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.api_version = api_version
        self._init_api()
        
    def _init_api(self):
        try:
            FacebookAdsApi.init(
                app_id=self.app_id,
                app_secret=self.app_secret,
                access_token=self.access_token,
                api_version=self.api_version
            )
            self.ad_account = AdAccount(self.ad_account_id)
            logger.info("✅ API Meta Ads initialisée")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation API Meta: {e}")
            raise

    @retry_on_rate_limit()
    def get_campaigns(self) -> List[Dict]:
        """Récupère UNIQUEMENT les campagnes ACTIVES ou EN PAUSE."""
        try:
            fields = [
                Campaign.Field.id, Campaign.Field.name, Campaign.Field.status,
                Campaign.Field.objective, Campaign.Field.daily_budget, Campaign.Field.lifetime_budget,
                Campaign.Field.start_time, Campaign.Field.stop_time,
                Campaign.Field.created_time, Campaign.Field.updated_time,
            ]
            
            # 🚨 FILTRAGE STRICT ICI
            params = {
                'limit': 500,
                'effective_status': ['ACTIVE', 'PAUSED'], # On exclut ARCHIVED et DELETED
            }
            
            logger.info("📊 Récupération des campagnes (ACTIVE/PAUSED)...")
            campaigns_iter = self.ad_account.get_campaigns(fields=fields, params=params)
            
            data = []
            for camp in campaigns_iter:
                daily = float(camp.get('daily_budget')) / 100 if camp.get('daily_budget') else None
                lifetime = float(camp.get('lifetime_budget')) / 100 if camp.get('lifetime_budget') else None
                
                data.append({
                    'campaign_id': camp['id'],
                    'campaign_name': camp['name'],
                    'status': camp['status'],
                    'objective': camp.get('objective'),
                    'daily_budget': daily,
                    'lifetime_budget': lifetime,
                    'start_time': camp.get('start_time'),
                    'end_time': camp.get('stop_time'),
                    'created_time': camp.get('created_time'),
                    'updated_time': camp.get('updated_time'),
                    'collected_at': datetime.now()
                })
            return data
        except Exception as e:
            logger.error(f"❌ Erreur campagnes: {e}")
            raise

    @retry_on_rate_limit()
    def get_adsets(self) -> List[Dict]:
        """Récupère les AdSets (ACTIVE/PAUSED)."""
        try:
            fields = [
                AdSet.Field.id, AdSet.Field.name, AdSet.Field.campaign_id, AdSet.Field.status,
                AdSet.Field.optimization_goal, AdSet.Field.billing_event,
                AdSet.Field.daily_budget, AdSet.Field.lifetime_budget,
                AdSet.Field.start_time, AdSet.Field.end_time, AdSet.Field.targeting,
            ]
            params = {
                'limit': 500,
                'effective_status': ['ACTIVE', 'PAUSED'] # Filtre strict
            }
            
            adsets_iter = self.ad_account.get_ad_sets(fields=fields, params=params)
            
            data = []
            for adset in adsets_iter:
                daily = float(adset.get('daily_budget')) / 100 if adset.get('daily_budget') else None
                lifetime = float(adset.get('lifetime_budget')) / 100 if adset.get('lifetime_budget') else None
                
                # Gestion JSON propre
                tgt = adset.get('targeting')
                if hasattr(tgt, 'export_all_data'):
                    tgt_json = json.dumps(tgt.export_all_data())
                else:
                    tgt_json = json.dumps(tgt) if tgt else None

                data.append({
                    'adset_id': adset['id'],
                    'adset_name': adset['name'],
                    'campaign_id': adset['campaign_id'],
                    'status': adset['status'],
                    'optimization_goal': adset.get('optimization_goal'),
                    'billing_event': adset.get('billing_event'),
                    'daily_budget': daily,
                    'lifetime_budget': lifetime,
                    'start_time': adset.get('start_time'),
                    'end_time': adset.get('end_time'),
                    'targeting': tgt_json,
                    'collected_at': datetime.now()
                })
            return data
        except Exception as e:
            logger.error(f"❌ Erreur adsets: {e}")
            raise

    @retry_on_rate_limit()
    def get_ads(self) -> List[Dict]:
        """Récupère les Ads (ACTIVE/PAUSED)."""
        try:
            fields = [
                Ad.Field.id, Ad.Field.name, Ad.Field.adset_id, Ad.Field.campaign_id,
                Ad.Field.status, Ad.Field.creative, Ad.Field.created_time, Ad.Field.updated_time
            ]
            params = {
                'limit': 500,
                'effective_status': ['ACTIVE', 'PAUSED'] # Filtre strict
            }
            
            ads_iter = self.ad_account.get_ads(fields=fields, params=params)
            
            data = []
            for ad in ads_iter:
                data.append({
                    'ad_id': ad['id'],
                    'ad_name': ad['name'],
                    'adset_id': ad['adset_id'],
                    'campaign_id': ad['campaign_id'],
                    'status': ad['status'],
                    'creative_id': ad.get('creative', {}).get('id'),
                    'created_time': ad.get('created_time'),
                    'updated_time': ad.get('updated_time'),
                    'collected_at': datetime.now()
                })
            return data
        except Exception as e:
            logger.error(f"❌ Erreur ads: {e}")
            raise

    @retry_on_rate_limit()
    def get_insights(self, level='ad', days=30) -> List[Dict]:
        """Récupère les statistiques (Insights)."""
        try:
            fields = [
                AdsInsights.Field.campaign_id, AdsInsights.Field.adset_id, AdsInsights.Field.ad_id,
                AdsInsights.Field.date_start, AdsInsights.Field.impressions, AdsInsights.Field.clicks,
                AdsInsights.Field.spend, AdsInsights.Field.reach, AdsInsights.Field.frequency,
                AdsInsights.Field.cpc, AdsInsights.Field.cpm, AdsInsights.Field.ctr,
                AdsInsights.Field.actions, # Contient le détail (link_click, video_view, etc.)
                AdsInsights.Field.action_values, 
                AdsInsights.Field.cost_per_action_type
            ]
            
            date_stop = datetime.now()
            date_start = date_stop - timedelta(days=days)
            
            params = {
                'level': level,
                'time_range': {
                    'since': date_start.strftime('%Y-%m-%d'),
                    'until': date_stop.strftime('%Y-%m-%d')
                },
                'time_increment': 1,
                'limit': 5000
            }
            
            logger.info(f"📊 Récupération Insights ({level}) sur {days} jours...")
            insights_iter = self.ad_account.get_insights(fields=fields, params=params)
            
            data = []
            for insight in insights_iter:
                actions = insight.get('actions', [])
                
                # --- CORRECTION DU CALCUL DES RÉSULTATS ---
                # Au lieu de tout sommer, on cherche les actions pertinentes pour la musique
                # Priorité : 
                # 1. 'link_click' (Clic vers Hypeddit/Spotify)
                # 2. 'offsite_conversion' (Si pixel configuré)
                # 3. Sinon 0
                
                relevant_action_types = ['link_click', 'offsite_conversion.custom']
                total_conversions = 0
                
                if actions:
                    for action in actions:
                        if action['action_type'] in relevant_action_types:
                            total_conversions += float(action['value'])
                            
                # Si total_conversions est 0 mais qu'on a des clics génériques, on peut prendre 'clicks'
                # Mais pour être strict sur le "Résultat", gardons link_click.
                
                # Récupération du coût par résultat (si dispo)
                cost_per_actions = insight.get('cost_per_action_type', [])
                cost_per_conv = 0.0
                if cost_per_actions:
                    for cpa in cost_per_actions:
                        if cpa['action_type'] in relevant_action_types:
                            cost_per_conv = float(cpa['value'])
                            break 

                record = {
                    'date': insight['date_start'],
                    'impressions': int(insight.get('impressions', 0)),
                    'clicks': int(insight.get('clicks', 0)), # Tous les clics (même sur le profil)
                    'spend': float(insight.get('spend', 0)),
                    'reach': int(insight.get('reach', 0)),
                    'frequency': float(insight.get('frequency', 0)),
                    'cpc': float(insight.get('cpc', 0)) if 'cpc' in insight else 0.0,
                    'cpm': float(insight.get('cpm', 0)) if 'cpm' in insight else 0.0,
                    'ctr': float(insight.get('ctr', 0)) if 'ctr' in insight else 0.0,
                    'conversions': int(total_conversions), # Maintenant c'est propre !
                    'cost_per_conversion': cost_per_conv,
                    'collected_at': datetime.now()
                }
                
                if level == 'ad': record['ad_id'] = insight['ad_id']
                if level == 'campaign': record['campaign_id'] = insight['campaign_id']
                
                data.append(record)
                
            return data
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération insights: {e}")
            raise