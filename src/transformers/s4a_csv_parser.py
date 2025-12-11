"""Parser S4A Intelligent (Supporte les CSV Timeline par fichier avec dates)."""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging
import re  # Indispensable pour gérer les noms de fichiers changeants

logger = logging.getLogger(__name__)

class S4ACSVParser:
    """Parse les CSV de Spotify for Artists."""
    
    def _extract_song_name_from_filename(self, filename: str) -> str:
        """
        Nettoie le nom du fichier pour extraire le titre.
        Transforme : "Mon Titre - Remix_20251129_180552.csv" -> "Mon Titre - Remix"
        """
        # 1. Enlève l'extension .csv
        name = Path(filename).stem
        
        # 2. REGEX : Supprime le pattern de date à la fin (_YYYYMMDD_HHMMSS)
        name = re.sub(r'_\d{8}_\d{6}$', '', name)
        
        # 3. Nettoyage des suffixes S4A classiques
        name = name.replace('-timeline', '').replace('_timeline', '')
        
        # 4. Nettoyage final
        return name.strip()

    def detect_csv_type(self, df: pd.DataFrame, filename: str = "") -> Optional[str]:
        """Détecte le type de CSV."""
        columns = set(df.columns.str.lower().str.strip())
        clean_name = self._extract_song_name_from_filename(filename)
        
        # Audience Globale
        if "audience" in clean_name.lower():
            return 'audience'

        # Timeline Chanson (Cas standard)
        if 'date' in columns:
            if any(col in columns for col in ['streams', 'ecoutes', 'écoutes']):
                return 'song_timeline_single'
        
        return None
    
    def parse_csv_file(self, file_path: Path) -> Dict:
        """Parse un fichier CSV."""
        try:
            # Lecture robuste (Header variable)
            try:
                df = pd.read_csv(file_path)
                if 'date' not in df.columns.str.lower() and len(df) > 0:
                     df = pd.read_csv(file_path, header=1)
            except:
                return {'type': None, 'data': []}

            df.columns = df.columns.str.strip().str.lower()
            
            # Identification
            csv_type = self.detect_csv_type(df, file_path.name)
            clean_song_name = self._extract_song_name_from_filename(file_path.name)
            
            data = []
            
            # Traitement Timeline Chanson
            if csv_type == 'song_timeline_single':
                # Trouver la colonne streams
                stream_col = next((c for c in df.columns if c in ['streams', 'ecoutes', 'écoutes']), None)
                
                if stream_col:
                    for _, row in df.iterrows():
                        try:
                            # Nettoyage valeur (ex: "1,024")
                            raw_val = str(row[stream_col])
                            val = int(raw_val.replace(',', '').replace(' ', '').split('.')[0])
                            
                            data.append({
                                'song': clean_song_name, # Nom PROPRE (sans date)
                                'date': pd.to_datetime(row['date']).date(),
                                'streams': val
                            })
                        except:
                            continue
                
                csv_type = 'song_timeline' 

            return {
                'type': csv_type,
                'data': data,
                'source_file': file_path.name
            }

        except Exception as e:
            logger.error(f"❌ Erreur parsing {file_path.name}: {e}")
            return {'type': None, 'data': []}