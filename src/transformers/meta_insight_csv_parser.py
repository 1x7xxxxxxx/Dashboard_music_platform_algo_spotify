import pandas as pd
import logging
from pathlib import Path
import warnings

warnings.simplefilter("ignore")
logger = logging.getLogger(__name__)

class MetaInsightParser:
    
    def _clean_currency(self, val):
        if pd.isna(val) or val == '': return 0.0
        if isinstance(val, (int, float)): return float(val)
        val = str(val).replace('€', '').replace('$', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
        try: return float(val)
        except: return 0.0

    def _clean_int(self, val):
        return int(self._clean_currency(val))

    def detect_file_type(self, df):
        cols = [str(c).lower() for c in df.columns]
        
        # 1. Identifier la Répartition
        breakdown = 'global'
        if any(k in str(cols) for k in ['plateforme', 'plate-forme', 'platform', 'placement']): 
            breakdown = 'placement'
        elif any('jour' in c for c in cols) or 'day' in cols: 
            breakdown = 'day'
        elif any('âge' in c for c in cols) or 'age' in cols: 
            breakdown = 'age'
        elif any('pays' in c for c in cols) or 'country' in cols: 
            breakdown = 'country'
        
        # 2. Identifier la Catégorie
        # Performance : contient Dépenses, Impressions ou Couverture
        is_performance = any(k in str(cols) for k in ['montant dépensé', 'amount spent', 'impressions', 'couverture', 'reach'])
        
        # Engagement : contient Interaction, Réaction ou Commentaire (et PAS les métriques purement financières)
        is_engagement = any(k in str(cols) for k in ['interaction', 'réaction', 'reaction', 'comment'])
        
        category = 'performance' # Par défaut
        if is_engagement and not is_performance:
            category = 'engagement'
        
        return f"{category}_{breakdown}"

    def read_flexible(self, file_path):
        try: return pd.read_excel(file_path, engine='openpyxl', header=None)
        except: pass
        try: return pd.read_csv(file_path, header=None)
        except: pass
        try: return pd.read_csv(file_path, sep=';', header=None)
        except: return pd.DataFrame()

    def parse_csv(self, file_path: Path):
        print(f"🔍 [Parser] Analyse : {file_path.name}")
        
        df_raw = self.read_flexible(file_path)
        if df_raw.empty: return {'type': 'error', 'data': []}

        # --- HEADER SCAN ---
        header_row, header_col = None, None
        found = False
        for r in range(min(20, len(df_raw))):
            for c in range(min(5, len(df_raw.columns))):
                val = str(df_raw.iat[r, c]).strip().lower()
                if "nom de la campagne" in val or "campaign name" in val:
                    header_row, header_col = r, c
                    found = True
                    break
            if found: break
        
        if header_row is None:
            print(f"❌ En-tête introuvable.")
            return {'type': 'error', 'data': []}

        # --- RECADRAGE ---
        df = df_raw.iloc[header_row+1:, header_col:].copy()
        cols = df_raw.iloc[header_row, header_col:].values
        df.columns = [str(x).strip().lower() for x in cols]
        
        # --- CLEAN CAMPAGNE ---
        camp_col = next((c for c in df.columns if 'nom de la campagne' in c or 'campaign name' in c), None)
        if not camp_col: return {'type': 'error', 'data': []}

        df[camp_col] = df[camp_col].ffill()
        df = df[df[camp_col].notna()]
        df = df[~df[camp_col].astype(str).str.lower().isin(['résultats', 'total', 'resultats'])]

        # --- DETECTION TYPE ---
        full_type = self.detect_file_type(df)
        print(f"   🏷️ Type identifié : {full_type.upper()}")

        # --- FFILL PLACEMENT ---
        if 'placement' in full_type:
            plat_col = next((c for c in df.columns if any(k in c for k in ['plate-forme', 'platform', 'plateforme'])), None)
            place_col = next((c for c in df.columns if 'placement' in c), None)
            if plat_col: df[plat_col] = df[plat_col].ffill()
            if place_col: df[place_col] = df[place_col].ffill()

        data = []
        def get_val(row, keywords, cleaner=None):
            col_name = next((c for c in df.columns if any(k in c for k in keywords)), None)
            if col_name: return cleaner(row[col_name]) if cleaner else row[col_name]
            return None

        for _, row in df.iterrows():
            entry = {}
            entry['campaign_name'] = row.get(camp_col)
            
            category, breakdown = full_type.split('_')
            
            # 1. RÉPARTITIONS
            if breakdown == 'placement':
                entry['platform'] = get_val(row, ['plate-forme', 'platform', 'plateforme'])
                entry['placement'] = get_val(row, ['placement'])
                if not entry['platform']: entry['platform'] = "Unknown"
                if not entry['placement']: entry['placement'] = "All"
            elif breakdown == 'day':
                try: entry['day_date'] = pd.to_datetime(get_val(row, ['jour', 'day'])).date()
                except: continue
            elif breakdown == 'age':
                entry['age_range'] = get_val(row, ['âge', 'age'])
            elif breakdown == 'country':
                entry['country'] = get_val(row, ['pays', 'country'])
                if not entry['country']: continue

            # 2. PERFORMANCE
            if category == 'performance':
                entry['spend'] = get_val(row, ['montant dépensé', 'amount spent'], self._clean_currency)
                entry['results'] = get_val(row, ['résultats', 'results'], self._clean_int)
                entry['cpr'] = get_val(row, ['coût par résultat', 'cost per result'], self._clean_currency)
                entry['impressions'] = get_val(row, ['impressions'], self._clean_int)
                entry['reach'] = get_val(row, ['couverture', 'reach'], self._clean_int)
                
                if breakdown == 'global':
                    entry['frequency'] = get_val(row, ['répétition', 'frequency'], self._clean_currency)
                    entry['link_clicks'] = get_val(row, ['clics sur un lien', 'link clicks'], self._clean_int)
                    entry['cpc'] = get_val(row, ['cpc', 'coût par clic'], self._clean_currency)
                    entry['ctr'] = get_val(row, ['ctr'], self._clean_currency)
                    entry['lp_views'] = get_val(row, ['vue de page', 'landing'], self._clean_int)
                    entry['cpm'] = get_val(row, ['cpm'], self._clean_currency)

            # 3. ENGAGEMENT (C'est ici que ça se joue)
            if category == 'engagement':
                # AJOUT de 'interaction' au singulier 👇
                entry['page_interactions'] = get_val(row, ['intéractions', 'interactions', 'interaction'], self._clean_int)
                entry['post_reactions'] = get_val(row, ['réaction', 'reaction'], self._clean_int)
                entry['comments'] = get_val(row, ['commentaire', 'comment'], self._clean_int)
                entry['saves'] = get_val(row, ['enregistrement', 'save'], self._clean_int)
                entry['shares'] = get_val(row, ['partage', 'share'], self._clean_int)
                entry['link_clicks'] = get_val(row, ['clics sur un lien', 'link clicks'], self._clean_int)
                entry['post_likes'] = get_val(row, ['j’aime', 'likes'], self._clean_int)

            data.append(entry)

        print(f"   ✅ {len(data)} lignes extraites.")
        return {'type': full_type, 'data': data}