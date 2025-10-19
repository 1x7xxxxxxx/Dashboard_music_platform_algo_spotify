"""Collector pour Meta Ads API."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adsinsights import AdsInsights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetaAdsCollector:
    """Collecte les données depuis Meta Ads API."""
    
    def __init__(self, app_id: str, app_secret: str, access_token: str, 
                 ad_account_id: str, api_version: str = "v21.0"):
        """
        Initialise le collector Meta Ads.
        
        Args:
            app_id: App ID Meta
            app_secret: App Secret
            access_token: Access Token
            ad_account_id: Ad Account ID (format: act_123456789)
            api_version: Version de l'API
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.api_version = api_version
        
        self._initialize_api()
    
    def _initialize_api(self) -> None:
        """Initialise l'API Meta Ads."""
        try:
            FacebookAdsApi.init(
                app_id=self.app_id,
                app_secret=self.app_secret,
                access_token=self.access_token,
                api_version=self.api_version
            )
            logger.info("✅ API Meta Ads initialisée")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation API: {e}")
            raise
    
    def get_campaigns(self) -> List[Dict[str, Any]]:
        """Récupère toutes les campagnes."""
        logger.info("📊 Récupération des campagnes...")
        
        try:
            account = AdAccount(self.ad_account_id)
            
            campaigns = account.get_campaigns(fields=[
                Campaign.Field.id,
                Campaign.Field.name,
                Campaign.Field.status,
                Campaign.Field.objective,
                Campaign.Field.daily_budget,
                Campaign.Field.lifetime_budget,
                Campaign.Field.start_time,
                Campaign.Field.stop_time,
                Campaign.Field.created_time,
                Campaign.Field.updated_time
            ])
            
            campaigns_data = []
            for campaign in campaigns:
                campaigns_data.append({
                    'campaign_id': campaign.get('id'),
                    'campaign_name': campaign.get('name'),
                    'status': campaign.get('status'),
                    'objective': campaign.get('objective'),
                    'daily_budget': float(campaign.get('daily_budget', 0)) / 100 if campaign.get('daily_budget') else None,
                    'lifetime_budget': float(campaign.get('lifetime_budget', 0)) / 100 if campaign.get('lifetime_budget') else None,
                    'start_time': campaign.get('start_time'),
                    'end_time': campaign.get('stop_time'),
                    'created_time': campaign.get('created_time'),
                    'updated_time': campaign.get('updated_time'),
                    'collected_at': datetime.now()
                })
            
            logger.info(f"✅ {len(campaigns_data)} campagnes récupérées")
            return campaigns_data
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération campagnes: {e}")
            return []
    
    def get_adsets(self, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère les adsets."""
        logger.info("📊 Récupération des adsets...")
        
        try:
            account = AdAccount(self.ad_account_id)
            
            params = {}
            if campaign_id:
                params['filtering'] = [{'field': 'campaign.id', 'operator': 'EQUAL', 'value': campaign_id}]
            
            adsets = account.get_ad_sets(
                fields=[
                    AdSet.Field.id,
                    AdSet.Field.name,
                    AdSet.Field.campaign_id,
                    AdSet.Field.status,
                    AdSet.Field.optimization_goal,
                    AdSet.Field.billing_event,
                    AdSet.Field.daily_budget,
                    AdSet.Field.lifetime_budget,
                    AdSet.Field.start_time,
                    AdSet.Field.end_time,
                    AdSet.Field.targeting
                ],
                params=params
            )
            
            adsets_data = []
            for adset in adsets:
                adsets_data.append({
                    'adset_id': adset.get('id'),
                    'adset_name': adset.get('name'),
                    'campaign_id': adset.get('campaign_id'),
                    'status': adset.get('status'),
                    'optimization_goal': adset.get('optimization_goal'),
                    'billing_event': adset.get('billing_event'),
                    'daily_budget': float(adset.get('daily_budget', 0)) / 100 if adset.get('daily_budget') else None,
                    'lifetime_budget': float(adset.get('lifetime_budget', 0)) / 100 if adset.get('lifetime_budget') else None,
                    'start_time': adset.get('start_time'),
                    'end_time': adset.get('end_time'),
                    'targeting': adset.get('targeting'),
                    'collected_at': datetime.now()
                })
            
            logger.info(f"✅ {len(adsets_data)} adsets récupérés")
            return adsets_data
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération adsets: {e}")
            return []
    
    def get_ads(self, adset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère les ads."""
        logger.info("📊 Récupération des ads...")
        
        try:
            account = AdAccount(self.ad_account_id)
            
            params = {}
            if adset_id:
                params['filtering'] = [{'field': 'adset.id', 'operator': 'EQUAL', 'value': adset_id}]
            
            ads = account.get_ads(
                fields=[
                    Ad.Field.id,
                    Ad.Field.name,
                    Ad.Field.adset_id,
                    Ad.Field.campaign_id,
                    Ad.Field.status,
                    Ad.Field.creative,
                    Ad.Field.created_time,
                    Ad.Field.updated_time
                ],
                params=params
            )
            
            ads_data = []
            for ad in ads:
                creative = ad.get('creative', {})
                ads_data.append({
                    'ad_id': ad.get('id'),
                    'ad_name': ad.get('name'),
                    'adset_id': ad.get('adset_id'),
                    'campaign_id': ad.get('campaign_id'),
                    'status': ad.get('status'),
                    'creative_id': creative.get('id') if isinstance(creative, dict) else None,
                    'created_time': ad.get('created_time'),
                    'updated_time': ad.get('updated_time'),
                    'collected_at': datetime.now()
                })
            
            logger.info(f"✅ {len(ads_data)} ads récupérées")
            return ads_data
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération ads: {e}")
            return []
    
    def get_insights(self, ad_id: str, days: int = 730) -> List[Dict[str, Any]]:
        """
        Récupère les insights pour une ad.
        
        Args:
            ad_id: ID de l'ad
            days: Nombre de jours d'historique
        """
        logger.info(f"📊 Récupération insights pour ad {ad_id}...")
        
        try:
            ad = Ad(ad_id)
            
            date_start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            date_end = datetime.now().strftime('%Y-%m-%d')
            
            insights = ad.get_insights(
                fields=[
                    AdsInsights.Field.date_start,
                    AdsInsights.Field.impressions,
                    AdsInsights.Field.clicks,
                    AdsInsights.Field.spend,
                    AdsInsights.Field.reach,
                    AdsInsights.Field.frequency,
                    AdsInsights.Field.cpc,
                    AdsInsights.Field.cpm,
                    AdsInsights.Field.ctr,
                    'conversions',
                    'cost_per_conversion'
                ],
                params={
                    'time_range': {'since': date_start, 'until': date_end},
                    'time_increment': 1,
                    'level': 'ad'
                }
            )
            
            insights_data = []
            for insight in insights:
                insights_data.append({
                    'ad_id': ad_id,
                    'date': insight.get('date_start'),
                    'impressions': int(insight.get('impressions', 0)),
                    'clicks': int(insight.get('clicks', 0)),
                    'spend': float(insight.get('spend', 0)),
                    'reach': int(insight.get('reach', 0)),
                    'frequency': float(insight.get('frequency', 0)),
                    'cpc': float(insight.get('cpc', 0)),
                    'cpm': float(insight.get('cpm', 0)),
                    'ctr': float(insight.get('ctr', 0)),
                    'conversions': int(insight.get('conversions', 0)) if insight.get('conversions') else 0,
                    'cost_per_conversion': float(insight.get('cost_per_conversion', 0)) if insight.get('cost_per_conversion') else 0,
                    'collected_at': datetime.now()
                })
            
            logger.info(f"✅ {len(insights_data)} jours d'insights récupérés")
            return insights_data
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération insights: {e}")
            return []
    
    def collect_all(self, days_insights: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collecte complète: campaigns, adsets, ads, insights.
        
        Args:
            days_insights: Nombre de jours d'insights à récupérer
            
        Returns:
            Dict avec toutes les données collectées
        """
        logger.info("\n" + "="*70)
        logger.info("🚀 COLLECTE META ADS COMPLÈTE")
        logger.info("="*70)
        
        data = {
            'campaigns': [],
            'adsets': [],
            'ads': [],
            'insights': []
        }
        
        # 1. Campaigns
        data['campaigns'] = self.get_campaigns()
        
        # 2. Adsets
        data['adsets'] = self.get_adsets()
        
        # 3. Ads
        data['ads'] = self.get_ads()
        
        # 4. Insights pour chaque ad
        for ad in data['ads']:
            ad_insights = self.get_insights(ad['ad_id'], days=days_insights)
            data['insights'].extend(ad_insights)
        
        logger.info("\n" + "="*70)
        logger.info("✅ COLLECTE TERMINÉE")
        logger.info("="*70)
        logger.info(f"📊 Campagnes : {len(data['campaigns'])}")
        logger.info(f"📊 Adsets    : {len(data['adsets'])}")
        logger.info(f"📊 Ads       : {len(data['ads'])}")
        logger.info(f"📊 Insights  : {len(data['insights'])}")
        logger.info("="*70 + "\n")
        
        return data


# Test
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config_loader import config_loader
    
    config = config_loader.load()
    meta_config = config['meta_ads']
    
    collector = MetaAdsCollector(
        app_id=meta_config['app_id'],
        app_secret=meta_config['app_secret'],
        access_token=meta_config['access_token'],
        ad_account_id=meta_config['ad_account_id'],
        api_version=meta_config.get('api_version', 'v21.0')
    )
    
    data = collector.collect_all(days_insights=7)