import pandas as pd
import logging
from pathlib import Path
import warnings
import re

# On ignore les warnings de style openpyxl
warnings.simplefilter("ignore")

logger = logging.getLogger(__name__)

class MetaInsightParser:
    
    def _clean_currency(self, val):
        if pd.isna(val) or val == '': return 0.0
        if isinstance(val, (int, float)): return float(val)
        # Nettoyage : symboles monétaires, espaces insécables (\xa0), espaces normaux
        val = str(val).replace('€', '').replace('$', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
        try: return float(val)
        except: return 0.0

    def _clean_int(self, val):
        return int(self._clean_currency(val))

    def detect_file_type(self, df):
        cols = [str(c).lower() for c in df.columns]
        
        if any('âge' in c for c in cols) or 'age' in cols: return 'age'
        if any('pays' in c for c in cols) or 'country' in cols: return 'country'
        if any('plate-forme' in c for c in cols) or 'platform' in cols or 'placement' in cols: return 'placement'
        if any('jour' in c for c in cols) or 'day' in cols: return 'day'
        
        engagement_keywords = ['réaction', 'reaction', 'commentaire', 'comment', 'partage', 'share']
        if any(k in str(cols) for k in engagement_keywords):
            return 'global_engagement'
        
        return 'global_performance'

    def read_flexible(self, file_path):
        """Tente de lire le fichier coûte que coûte (Excel ou CSV déguisé)."""
        errors = []
        
        # 1. Tentative Excel (Standard)
        try:
            # Header None pour tout scanner
            return pd.read_excel(file_path, engine='openpyxl', header=None) 
        except Exception as e:
            errors.append(f"Excel: {e}")
        
        # 2. Tentative CSV (Virgule)
        try:
            return pd.read_csv(file_path, header=None)
        except Exception as e:
            errors.append(f"CSV(,): {e}")

        # 3. Tentative CSV (Point-virgule)
        try:
            return pd.read_csv(file_path, sep=';', header=None)
        except Exception as e:
            errors.append(f"CSV(;): {e}")
            
        print(f"❌ Échec lecture fichier : {errors}")
        return pd.DataFrame()

    def parse_csv(self, file_path: Path):
        print(f"🔍 [Parser] Analyse : {file_path.name}")
        
        # 1. Lecture Brute
        df_raw = self.read_flexible(file_path)
        
        if df_raw.empty:
            return {'type': 'error', 'data': []}

        # 2. Recherche du Header (Ligne contenant "Nom de la campagne")
        header_idx = None
        
        # On scanne les 20 premières lignes
        for r in range(min(20, len(df_raw))):
            row_vals = [str(x).strip().lower() for x in df_raw.iloc[r].values if pd.notna(x)]
            # On cherche large : 'campaign' ou 'campagne'
            if any("nom de la campagne" in x or "campaign name" in x for x in row_vals):
                header_idx = r
                break
        
        if header_idx is None:
            print(f"❌ Impossible de trouver l'en-tête 'Nom de la campagne' dans les 20 premières lignes.")
            # Debug : Afficher la première ligne non vide pour comprendre
            print(f"   Aperçu ligne 0 : {df_raw.iloc[0].values}")
            return {'type': 'error', 'data': []}

        print(f"   📍 Header trouvé ligne {header_idx}")

        # 3. Re-construction du DataFrame propre
        # On prend la ligne identifiée comme header
        df = df_raw.iloc[header_idx+1:].copy()
        df.columns = df_raw.iloc[header_idx].values
        
        # Nettoyage des noms de colonnes
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        # 4. Identification colonne clé
        camp_col = next((c for c in df.columns if 'nom de la campagne' in c or 'campaign name' in c), None)
        
        if not camp_col:
            print(f"❌ Colonne campagne perdue après formatage. Colonnes : {list(df.columns)}")
            return {'type': 'error', 'data': []}

        # 5. Nettoyage Données
        # Pour Excel : on propage le nom de campagne vers le bas (cellules fusionnées)
        df[camp_col] = df[camp_col].ffill()
        df = df[df[camp_col].notna()]
        # On vire les lignes "Total" ou "Résultats"
        df = df[~df[camp_col].astype(str).str.lower().isin(['résultats', 'total', 'resultats'])]

        file_type = self.detect_file_type(df)
        print(f"   🏷️ Type : {file_type.upper()}")

        data = []
        
        # Helper extraction souple
        def get_val(row, keywords, cleaner=None):
            # Cherche correspondance exacte ou partielle
            col_name = next((c for c in df.columns if any(k in c for k in keywords)), None)
            if col_name:
                return cleaner(row[col_name]) if cleaner else row[col_name]
            return None

        for _, row in df.iterrows():
            entry = {}
            entry['campaign_name'] = row.get(camp_col)
            
            # --- Commun ---
            entry['spend'] = get_val(row, ['montant dépensé', 'amount spent'], self._clean_currency)
            entry['results'] = get_val(row, ['résultats', 'results'], self._clean_int)
            entry['cpr'] = get_val(row, ['coût par résultat', 'cost per result'], self._clean_currency)
            entry['impressions'] = get_val(row, ['impressions'], self._clean_int)
            entry['reach'] = get_val(row, ['couverture', 'reach'], self._clean_int)

            # --- Performance ---
            if file_type == 'global_performance':
                entry['frequency'] = get_val(row, ['répétition', 'frequency'], self._clean_currency)
                entry['cpm'] = get_val(row, ['cpm'], self._clean_currency)
                entry['link_clicks'] = get_val(row, ['clics sur un lien', 'link clicks'], self._clean_int)
                # Attention : il y a souvent 2 CPC (CPC tous et CPC lien). On vise CPC lien.
                entry['cpc'] = get_val(row, ['cpc (coût par clic sur un lien)', 'cost per link click'], self._clean_currency)
                # Si pas trouvé, on cherche juste 'cpc'
                if not entry['cpc']: 
                     entry['cpc'] = get_val(row, ['cpc'], self._clean_currency)
                
                entry['ctr'] = get_val(row, ['ctr'], self._clean_currency)
                entry['lp_views'] = get_val(row, ['vue de page', 'landing'], self._clean_int)

            # --- Engagement ---
            elif file_type == 'global_engagement':
                entry['page_interactions'] = get_val(row, ['intéractions', 'interactions'], self._clean_int)
                entry['post_reactions'] = get_val(row, ['réaction', 'reaction'], self._clean_int)
                entry['comments'] = get_val(row, ['commentaire', 'comment'], self._clean_int)
                entry['saves'] = get_val(row, ['enregistrement', 'save'], self._clean_int)
                entry['shares'] = get_val(row, ['partage', 'share'], self._clean_int)
            
            # --- Répartitions ---
            elif file_type == 'age':
                entry['age_range'] = get_val(row, ['âge', 'age'])
                entry['page_interactions'] = get_val(row, ['intéractions', 'interactions'], self._clean_int)
            elif file_type == 'country':
                entry['country'] = get_val(row, ['pays', 'country'])
            elif file_type == 'placement':
                entry['platform'] = get_val(row, ['plate-forme', 'platform'])
                entry['placement'] = get_val(row, ['placement'])
            elif file_type == 'day':
                try: entry['day_date'] = pd.to_datetime(get_val(row, ['jour', 'day'])).date()
                except: continue

            data.append(entry)

        print(f"   ✅ {len(data)} lignes extraites.")
        return {'type': file_type, 'data': data}