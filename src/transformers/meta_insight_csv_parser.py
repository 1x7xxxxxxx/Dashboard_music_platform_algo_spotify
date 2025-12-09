import pandas as pd
import logging
import unicodedata
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class MetaInsightCSVParser:
    """
    Parse les exports CSV d'Insights Meta Ads.
    Version V5 Finale : Robuste, Nettoyage des Totaux, Mapping FR/EN.
    """

    def _normalize_str(self, text):
        """Nettoie une chaine : minuscule, sans accent, sans espace inutile."""
        if not isinstance(text, str): return str(text)
        # Décomposition des accents (ex: Â -> A)
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode("utf-8")
        return text.lower().strip()

    def _read_file_robust(self, file_path: Path):
        """Lit le fichier en testant plusieurs configurations d'encodage et de séparateur."""
        # Liste des configurations à tester (Ordre : UTF-8 (Standard), UTF-16 (Excel), Latin-1 (Vieux Excel))
        configs = [
            {'sep': ',', 'encoding': 'utf-8'},
            {'sep': ',', 'encoding': 'utf-8-sig'}, # UTF-8 avec BOM
            {'sep': '\t', 'encoding': 'utf-16'},   # Export brut
            {'sep': ',', 'encoding': 'latin-1'},
            {'sep': ';', 'encoding': 'latin-1'}    # Format Excel FR parfois
        ]
        
        for cfg in configs:
            try:
                # On lit tout le fichier en ignorant les lignes malformées
                df = pd.read_csv(file_path, on_bad_lines='skip', **cfg)
                
                # Vérification rapide : A-t-on des colonnes cohérentes ?
                cols = [self._normalize_str(c) for c in df.columns]
                
                # Critère de succès : On cherche 'campagne' ET ('date' ou 'debut' ou 'start')
                has_campaign = any('campagne' in c or 'campaign' in c for c in cols)
                
                if has_campaign and len(df.columns) > 3:
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
            # Map : { 'nom_normalise': 'Nom Réel dans le CSV' }
            col_map = {self._normalize_str(c): c for c in df.columns}
            cols_norm = list(col_map.keys())

            # --- 2. FILTRAGE DES LIGNES PARASITES (Totaux, Vides) ---
            # On cherche la colonne "Nom de la campagne"
            camp_col_norm = next((c for c in cols_norm if 'nom de la campagne' in c or 'campaign name' in c), None)
            
            if camp_col_norm:
                real_camp_col = col_map[camp_col_norm]
                # On supprime les lignes où le nom de la campagne est vide (ce sont les totaux)
                df = df.dropna(subset=[real_camp_col])
                # On supprime aussi si c'est juste des espaces
                df = df[df[real_camp_col].astype(str).str.strip() != '']
            
            # On cherche la colonne "Début des rapports" pour supprimer les lignes vides
            date_col_norm = next((c for c in cols_norm if 'debut' in c or 'start' in c), None)
            if date_col_norm:
                df = df.dropna(subset=[col_map[date_col_norm]])

            # Filtre Archives (Si la colonne existe)
            status_col_norm = next((c for c in cols_norm if 'diffusion' in c or 'status' in c), None)
            if status_col_norm:
                status_real = col_map[status_col_norm]
                # On filtre tout ce qui contient 'archiv' ou 'supprim'
                df = df[~df[status_real].astype(str).str.lower().str.contains('archiv|supprim|deleted', na=False, regex=True)]

            if df.empty:
                logger.warning("⚠️ Fichier vide après filtrage (Archives ou Totaux).")
                return None

            # --- 3. DÉTECTION DU TYPE & MAPPING ---
            result_type = 'unknown'
            data = None
            
            # Mapping Cible (BDD) -> Liste de Patterns possibles dans le CSV (Normalisés)
            base_mapping = {
                'campaign_name': ['nom de la campagne', 'campaign name'],
                'spend': ['montant depense', 'amount spent'],
                'impressions': ['impressions'],
                'clicks': ['clics', 'clicks'],  # ✅ On récupère bien les clics
                'reach': ['couverture', 'reach'],
                'results': ['resultats', 'results'],
                'date_start': ['debut des rapports', 'reporting starts'],
                'date_stop': ['fin des rapports', 'reporting ends']
            }

            def build_df(target_type, specific_map={}):
                """Construit le DataFrame final en cherchant les colonnes."""
                final_cols = {}
                
                # 1. Colonnes de base (Spend, Clics...)
                for db_col, patterns in base_mapping.items():
                    # On cherche la première colonne du CSV qui matche un des patterns
                    found = next((col_map[c] for c in cols_norm for p in patterns if p in c), None)
                    if found: 
                        final_cols[found] = db_col
                
                # 2. Colonnes spécifiques (Age, Pays...)
                for db_col, patterns in specific_map.items():
                    # Recherche exacte ou partielle
                    found = next((col_map[c] for c in cols_norm for p in patterns if p == c or p in c), None)
                    if found: 
                        final_cols[found] = db_col
                
                return df[list(final_cols.keys())].rename(columns=final_cols).copy()

            # --- LOGIQUE DE DÉTECTION (Ordre important) ---
            
            # 1. PLACEMENT (Doit avoir 'plateforme' et 'placement')
            if any('plateforme' in c for c in cols_norm) and any('placement' in c for c in cols_norm):
                result_type = 'platform'
                data = build_df('platform', {
                    'platform': ['plateforme', 'platform'],
                    'placement': ['placement'],
                    'device': ['appareil', 'device']
                })

            # 2. PAYS ('pays' ou 'country')
            elif any('pays' == c or 'country' == c for c in cols_norm): 
                result_type = 'country'
                data = build_df('country', {'country': ['pays', 'country']})

            # 3. AGE ('age' ou 'age')
            elif any('age' == c for c in cols_norm): 
                result_type = 'age'
                data = build_df('age', {'age_range': ['age']})

            # 4. GLOBAL (Par défaut, si on a le nom de campagne)
            elif any('nom de la campagne' in c for c in cols_norm):
                result_type = 'global'
                data = build_df('global')

            else:
                logger.error(f"❌ Type non identifié. Colonnes normalisées vues : {cols_norm}")
                return None

            # --- 4. NETTOYAGE DES VALEURS ---
            numeric_cols = ['spend', 'impressions', 'reach', 'results', 'clicks']
            for col in numeric_cols:
                if col in data.columns:
                    # Nettoyage robuste (1 200,50 -> 1200.50)
                    data[col] = (data[col].astype(str)
                                .str.replace(',', '.', regex=False)
                                .str.replace(r'[^\d\.-]', '', regex=True))
                    data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
            
            # Ajout timestamp
            data['collected_at'] = datetime.now()
            
            logger.info(f"   ✅ Type validé : {result_type.upper()} ({len(data)} lignes)")
            return {
                'type': result_type,
                'data': data
            }

        except Exception as e:
            logger.error(f"❌ Erreur critique {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            return None