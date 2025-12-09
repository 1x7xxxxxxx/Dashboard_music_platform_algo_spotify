import pandas as pd
import logging
import unicodedata
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class MetaInsightCSVParser:
    """
    Parse les exports CSV d'Insights Meta Ads.
    Version V5 : Suppression stricte des lignes de TOTAL (Campagne vide).
    """

    def _normalize_str(self, text):
        """Nettoie une chaine : minuscule, sans accent."""
        if not isinstance(text, str): return str(text)
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode("utf-8")
        return text.lower().strip()

    def _read_file_robust(self, file_path: Path):
        """Lit le fichier en testant plusieurs configurations."""
        configs = [
            {'sep': ',', 'encoding': 'utf-8', 'quotechar': '"'},
            {'sep': ',', 'encoding': 'utf-16', 'quotechar': '"'},
            {'sep': '\t', 'encoding': 'utf-16', 'quotechar': '"'},
            {'sep': ',', 'encoding': 'latin-1', 'quotechar': '"'},
        ]
        
        for cfg in configs:
            try:
                df = pd.read_csv(file_path, on_bad_lines='skip', **cfg)
                cols = [self._normalize_str(c) for c in df.columns]
                
                # Critère : On cherche 'campagne' ET ('date' ou 'debut' ou 'start')
                has_campaign = any('campagne' in c or 'campaign' in c for c in cols)
                has_date = any('debut' in c or 'start' in c or 'date' in c for c in cols)
                
                if has_campaign and has_date:
                    logger.info(f"   ✅ Format détecté : {cfg['encoding']} / '{cfg['sep']}'")
                    return df
            except Exception:
                continue
        return None

    def parse(self, file_path: Path):
        try:
            logger.info(f"📊 Analyse : {file_path.name}")
            
            df = self._read_file_robust(file_path)
            
            if df is None:
                logger.error("❌ Echec lecture : Aucun format ne correspond.")
                return None

            # --- 1. NORMALISATION DES COLONNES ---
            col_map = {self._normalize_str(c): c for c in df.columns}
            cols_norm = list(col_map.keys())

            # --- 2. FILTRAGE TOTAL / LIGNES VIDES (Nouveau !) ---
            # On cherche la colonne qui contient le nom de la campagne
            camp_col_norm = next((c for c in cols_norm if 'nom de la campagne' in c or 'campaign name' in c), None)
            
            if camp_col_norm:
                real_camp_col = col_map[camp_col_norm]
                
                # 1. On supprime les NaN dans la colonne campagne
                df = df.dropna(subset=[real_camp_col])
                
                # 2. On supprime les chaines vides ou espaces
                df = df[df[real_camp_col].astype(str).str.strip() != '']
                
                # 3. On supprime la ligne qui contient littéralement "Results from..." ou "Résultats" si elle existe
                df = df[~df[real_camp_col].astype(str).str.contains('Résultats', na=False)]
            else:
                logger.warning("⚠️ Impossible de trouver la colonne 'Nom de la campagne' pour filtrer les totaux.")

            # Filtre Archives
            status_col_norm = next((c for c in cols_norm if 'diffusion' in c or 'status' in c), None)
            if status_col_norm:
                status_real = col_map[status_col_norm]
                df = df[~df[status_real].astype(str).str.lower().str.contains('archiv', na=False)]

            if df.empty:
                logger.warning("⚠️ Fichier vide après filtrage.")
                return None

            # --- 3. DÉTECTION DU TYPE ---
            result_type = 'unknown'
            data = None
            
            base_mapping = {
                'campaign_name': ['nom de la campagne', 'campaign name'],
                'spend': ['montant depense', 'amount spent'],
                'impressions': ['impressions'],
                'reach': ['couverture', 'reach'],
                'results': ['resultats', 'results'],
                'date_start': ['debut des rapports', 'reporting starts'],
                'date_stop': ['fin des rapports', 'reporting ends']
            }

            def build_df(target_type, specific_map={}):
                final_cols = {}
                for db_col, patterns in base_mapping.items():
                    found = next((col_map[c] for c in cols_norm for p in patterns if p in c), None)
                    if found: final_cols[found] = db_col
                
                for db_col, patterns in specific_map.items():
                    found = next((col_map[c] for c in cols_norm for p in patterns if p == c or p in c), None)
                    if found: final_cols[found] = db_col
                
                return df[list(final_cols.keys())].rename(columns=final_cols).copy()

            # LOGIQUE DE DÉTECTION
            if any('plateforme' in c for c in cols_norm) and any('placement' in c for c in cols_norm):
                result_type = 'platform'
                data = build_df('platform', {
                    'platform': ['plateforme', 'platform'],
                    'placement': ['placement'],
                    'device': ['appareil', 'device']
                })

            elif any('pays' == c or 'country' == c for c in cols_norm):
                result_type = 'country'
                data = build_df('country', {'country': ['pays', 'country']})

            elif any('age' == c for c in cols_norm):
                result_type = 'age'
                data = build_df('age', {'age_range': ['age']})

            elif any('nom de la campagne' in c for c in cols_norm):
                result_type = 'global'
                data = build_df('global')

            else:
                logger.error(f"❌ Type non identifié.")
                return None

            # --- 4. NETTOYAGE VALEURS ---
            numeric_cols = ['spend', 'impressions', 'reach', 'results']
            for col in numeric_cols:
                if col in data.columns:
                    data[col] = (data[col].astype(str)
                                .str.replace(',', '.', regex=False)
                                .str.replace(r'[^\d\.-]', '', regex=True))
                    data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
            
            data['collected_at'] = datetime.now()
            
            logger.info(f"   ✅ Type validé : {result_type.upper()} ({len(data)} lignes)")
            return {
                'type': result_type,
                'data': data
            }

        except Exception as e:
            logger.error(f"❌ Erreur critique {file_path.name}: {e}")
            return None