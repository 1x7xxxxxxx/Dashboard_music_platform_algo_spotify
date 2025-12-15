import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
import warnings

warnings.simplefilter("ignore")
logger = logging.getLogger(__name__)

class MetaCSVParser:
    """
    Parser Configuration Meta complet (Campagnes, Adsets, Ads + Ciblage + Créa).
    """

    def read_flexible(self, file_path):
        """Lecture robuste (Tabulation + UTF-16 en priorité pour Meta)."""
        try: return pd.read_csv(file_path, sep='\t', encoding='utf-16', on_bad_lines='skip')
        except: pass
        try: return pd.read_csv(file_path, sep='\t', encoding='utf-8', on_bad_lines='skip')
        except: pass
        try: return pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip') # Cas virgule
        except: pass
        return pd.DataFrame()

    def parse(self, file_path: Path):
        print(f"🔧 [Config Parser] Analyse : {file_path.name}")
        
        df = self.read_flexible(file_path)
        
        # Scan pour trouver le header si le fichier a des lignes parasites au début
        if df.empty or 'Campaign ID' not in [str(c).strip() for c in df.columns]:
            # Mode Scan manuel
            df_raw = self.read_flexible(file_path) # Reload brut
            header_idx = None
            for r in range(min(20, len(df_raw))):
                row_str = [str(x).strip() for x in df_raw.iloc[r].values]
                if 'Campaign ID' in row_str:
                    header_idx = r
                    break
            
            if header_idx is not None:
                df = df_raw.iloc[header_idx+1:].copy()
                df.columns = [str(x).strip() for x in df_raw.iloc[header_idx].values]
            else:
                print("❌ Impossible de trouver l'en-tête 'Campaign ID'")
                return {'type': 'error', 'data': None}

        # Nettoyage des noms de colonnes
        df.columns = [str(c).strip() for c in df.columns]
        cols = df.columns.tolist()

        # Dictionnaires résultats
        campaigns, adsets, ads = {}, {}, {}

        # Helper pour récupérer une valeur (tolérant à la casse)
        def get_val(row, col_name):
            # Cherche correspondance exacte ou insensible à la casse
            target = next((c for c in cols if c.lower() == col_name.lower()), None)
            val = row[target] if target else None
            return str(val).strip() if pd.notna(val) else None

        for _, row in df.iterrows():
            
            # --- 1. CAMPAGNES ---
            c_id = get_val(row, 'Campaign ID')
            if c_id:
                c_id = c_id.replace('.0', '')
                campaigns[c_id] = {
                    'campaign_id': c_id,
                    'campaign_name': get_val(row, 'Campaign Name'),
                    'start_time': get_val(row, 'Campaign Start Time')
                }

            # --- 2. ADSETS (Ensembles) ---
            as_id = get_val(row, 'Ad Set ID')
            if as_id:
                as_id = as_id.replace('.0', '')
                adsets[as_id] = {
                    'adset_id': as_id,
                    'campaign_id': c_id,
                    'adset_name': get_val(row, 'Ad Set Name'),
                    'status': get_val(row, 'Ad Set Run Status') or get_val(row, 'Ad Set Status'), # Fallback
                    'start_time': get_val(row, 'Ad Set Time Start'),
                    
                    # Ciblage Géographique & Démographique
                    'countries': get_val(row, 'Countries'),
                    'cities': get_val(row, 'Cities'),
                    'gender': get_val(row, 'Gender'),
                    'age_min': get_val(row, 'Age Min'),
                    'age_max': get_val(row, 'Age Max'),
                    
                    # Ciblage Avancé
                    'flexible_inclusions': get_val(row, 'Flexible Inclusions'),
                    'advantage_audience': get_val(row, 'Advantage Audience'),
                    'age_range': get_val(row, 'Age Range'),
                    'targeting_optimization': get_val(row, 'Targeting Optimization'),
                    
                    # Placements
                    'publisher_platforms': get_val(row, 'Publisher Platforms'),
                    'instagram_positions': get_val(row, 'Instagram Positions'),
                    'device_platforms': get_val(row, 'Device Platforms')
                }

            # --- 3. ADS (Publicités) ---
            ad_id = get_val(row, 'Ad ID')
            if ad_id:
                ad_id = ad_id.replace('.0', '')
                ads[ad_id] = {
                    'ad_id': ad_id,
                    'adset_id': as_id,
                    'campaign_id': c_id,
                    'ad_name': get_val(row, 'Ad Name'),
                    
                    # Créa
                    'title': get_val(row, 'Title'),
                    'body': get_val(row, 'Body'),
                    'video_file_name': get_val(row, 'Video File Name'),
                    'call_to_action': get_val(row, 'Call to Action')
                }

        res_c = list(campaigns.values())
        res_as = list(adsets.values())
        res_ad = list(ads.values())

        print(f"   📊 Extraction : {len(res_c)} Camps | {len(res_as)} Sets | {len(res_ad)} Pubs")
        
        return {
            'type': 'mixed_config',
            'data': {'campaigns': res_c, 'adsets': res_as, 'ads': res_ad}
        }