"""Parser S4A Intelligent (Supporte les CSV Timeline par fichier)."""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)

class S4ACSVParser:
    """Parse les CSV de Spotify for Artists."""
    
    def detect_csv_type(self, df: pd.DataFrame, filename: str = "") -> Optional[str]:
        """Détecte le type de CSV."""
        columns = set(df.columns.str.lower().str.strip())
        
        # 1. CSV Global (Plusieurs chansons)
        if 'song' in columns or 'titre' in columns:
            if 'date' in columns:
                return 'song_timeline_multi' # Timeline multi-chansons
            return 'songs_global'
            
        # 2. CSV Timeline (Une seule chanson, nom dans le fichier)
        # Structure typique : date, streams
        if 'date' in columns and ('streams' in columns or 'écoutes' in columns):
            # Si le nom du fichier contient "-timeline", c'est un indicateur fort
            if "-timeline" in filename or "timeline" in filename.lower():
                return 'song_timeline_single'
            
            # Sinon, ça pourrait être l'audience globale
            return 'audience'
        
        return None
    
    def _extract_song_name_from_filename(self, filename: str) -> str:
        """Nettoie le nom du fichier pour extraire le titre."""
        # Enlève l'extension
        name = Path(filename).stem
        # Enlève les suffixes courants S4A
        name = name.replace('-timeline', '').replace('_timeline', '')
        # Enlève "- Original", "- Remix", etc si tu veux, ou garde-les
        return name.strip()

    def parse_csv_file(self, file_path: Path) -> Dict:
        """Parse un fichier CSV."""
        logger.info(f"\n📄 Lecture du fichier: {file_path.name}")
        
        try:
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip().str.lower()
            
            csv_type = self.detect_csv_type(df, file_path.name)
            logger.info(f"   🏷️ Type détecté: {csv_type}")
            
            data = []
            
            # CAS 1 : Timeline d'une seule chanson (Ton cas actuel)
            if csv_type == 'song_timeline_single':
                song_name = self._extract_song_name_from_filename(file_path.name)
                logger.info(f"   🎵 Chanson identifiée via fichier: {song_name}")
                
                # Trouver la colonne streams
                stream_col = next((c for c in df.columns if 'stream' in c or 'écoute' in c), None)
                
                if stream_col:
                    for _, row in df.iterrows():
                        try:
                            data.append({
                                'song': song_name,
                                'date': pd.to_datetime(row['date']).date(),
                                'streams': int(row[stream_col]),
                                'collected_at': datetime.now()
                            })
                        except Exception as e:
                            pass
                # On normalise le type pour le reste du pipeline
                csv_type = 'song_timeline'

            # CAS 2 : Audience Globale
            elif csv_type == 'audience':
                for _, row in df.iterrows():
                    data.append({
                        'date': pd.to_datetime(row['date']).date(),
                        'listeners': int(row.get('listeners', row.get('auditeurs', 0))),
                        'streams': int(row.get('streams', row.get('écoutes', 0))),
                        'followers': int(row.get('followers', row.get('abonnés', 0))),
                        'collected_at': datetime.now()
                    })

            # CAS 3 : Global Songs (Tableau récap)
            elif csv_type == 'songs_global':
                # (Logique existante pour le global)
                col_map = {
                    'song': next((c for c in df.columns if c in ['song', 'titre', 'track']), None),
                    'streams': next((c for c in df.columns if 'stream' in c), None)
                }
                if col_map['song']:
                    for _, row in df.iterrows():
                        data.append({
                            'song': row[col_map['song']],
                            'streams': int(row.get(col_map['streams'], 0)),
                            'collected_at': datetime.now()
                        })

            return {
                'type': csv_type,
                'data': data,
                'source_file': file_path.name
            }

        except Exception as e:
            logger.error(f"❌ Erreur parsing: {e}")
            return {'type': None, 'data': []}