import pandas as pd
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class MetaCSVParser:
    """
    Parse les exports CSV Meta Ads avec mapping strict des colonnes demandées.
    """

    def parse(self, file_path: Path):
        try:
            logger.info(f"📂 Lecture du fichier : {file_path.name}")
            
            # 1. Lecture Robuste (Gestion Tabulations \t et Encodage)
            # Votre fichier est un .csv qui utilise des tabulations
            try:
                df = pd.read_csv(file_path, sep='\t', encoding='utf-16', on_bad_lines='skip')
                if 'Campaign ID' not in df.columns:
                    raise ValueError("Mauvais encodage")
            except:
                try:
                    df = pd.read_csv(file_path, sep='\t', encoding='utf-8', on_bad_lines='skip')
                except:
                    # Moteur Python plus tolérant
                    df = pd.read_csv(file_path, sep='\t', engine='python')

            # Nettoyage des noms de colonnes (espaces avant/après)
            df.columns = [c.strip() for c in df.columns]
            
            if 'Campaign ID' not in df.columns:
                logger.error("❌ Colonne 'Campaign ID' introuvable.")
                return None

            # Remplacement des NaN par None (NULL en SQL) pour éviter les erreurs
            df = df.where(pd.notnull(df), None)

            # =================================================================
            # 1. CAMPAGNES
            # =================================================================
            camp_mapping = {
                'Campaign ID': 'campaign_id',
                'Campaign Name': 'campaign_name',
                'Campaign Start Time': 'start_time'
            }
            
            # Sélection et renommage
            df_camp = df[list(camp_mapping.keys())].rename(columns=camp_mapping).copy()
            df_camp = df_camp.drop_duplicates(subset=['campaign_id'])
            df_camp['collected_at'] = datetime.now()

            # =================================================================
            # 2. ADSETS
            # =================================================================
            # Mapping Colonne CSV -> Colonne BDD
            adset_mapping = {
                'Ad Set ID': 'adset_id',
                'Campaign ID': 'campaign_id', # Nécessaire pour la liaison
                'Ad Set Name': 'adset_name',
                'Ad Set Run Status': 'status',
                'Ad Set Time Start': 'start_time',
                'Countries': 'countries',
                'Gender': 'gender',
                'Age Min': 'age_min',
                'Age Max': 'age_max',
                'Advantage Audience': 'advantage_audience',
                'Age Range': 'age_range',
                'Publisher Platforms': 'publisher_platforms',
                'Instagram Positions': 'instagram_positions',
                'Device Platforms': 'device_platforms'
            }
            
            # On ne garde que les colonnes qui existent dans le fichier
            existing_cols = [c for c in adset_mapping.keys() if c in df.columns]
            df_adsets = df[existing_cols].rename(columns=adset_mapping).copy()
            
            # Nettoyage
            df_adsets = df_adsets.dropna(subset=['adset_id'])
            df_adsets = df_adsets.drop_duplicates(subset=['adset_id'])
            df_adsets['collected_at'] = datetime.now()

            # =================================================================
            # 3. ADS
            # =================================================================
            ads_mapping = {
                'Ad ID': 'ad_id',
                'Ad Set ID': 'adset_id',     # Nécessaire pour liaison
                'Campaign ID': 'campaign_id', # Nécessaire pour liaison
                'Ad Name': 'ad_name',
                'Instagram Preview Link': 'instagram_preview_link',
                'Dynamic Creative Ad Format': 'dynamic_creative_ad_format',
                'Default Language': 'default_language',
                'Additional Language 1': 'additional_language_1',
                'Title': 'title',
                'Additional Title 1': 'additional_title_1',
                'Body': 'body',
                'Additional Body 1': 'additional_body_1',
                'Additional Body 2': 'additional_body_2',
                'Additional Body 3': 'additional_body_3',
                'Link Description': 'link_description',
                'Additional Link Description 1': 'additional_link_description_1',
                'Video File Name': 'video_file_name',
                'Call to Action': 'call_to_action'
            }

            existing_cols = [c for c in ads_mapping.keys() if c in df.columns]
            df_ads = df[existing_cols].rename(columns=ads_mapping).copy()
            
            df_ads = df_ads.dropna(subset=['ad_id'])
            df_ads = df_ads.drop_duplicates(subset=['ad_id'])
            df_ads['collected_at'] = datetime.now()

            return {
                'campaigns': df_camp,
                'adsets': df_adsets,
                'ads': df_ads
            }

        except Exception as e:
            logger.error(f"❌ Erreur critique parsing CSV: {e}")
            raise