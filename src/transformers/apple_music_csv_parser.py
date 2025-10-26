"""Parser pour les CSV Apple Music for Artists."""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppleMusicCSVParser:
    """Parse les CSV d'Apple Music for Artists."""
    
    def __init__(self):
        """Initialise le parser."""
        pass
    
    def detect_csv_type(self, df: pd.DataFrame) -> Optional[str]:
        """
        Détecte le type de CSV Apple Music.
        
        Args:
            df: DataFrame pandas
            
        Returns:
            Type de CSV ou None
        """
        columns = set(df.columns.str.lower().str.strip())
        
        # CSV "Songs Performance"
        if 'song title' in columns or 'song' in columns:
            return 'songs_performance'
        
        # CSV "Daily Plays"
        if 'date' in columns and ('plays' in columns or 'plays' in ' '.join(df.columns).lower()):
            return 'daily_plays'
        
        # CSV "Listeners"
        if 'listeners' in columns or 'unique listeners' in ' '.join(df.columns).lower():
            return 'listeners'
        
        return None
    
    def parse_songs_performance(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV de performance des chansons.
        
        Format: Song Title, Album, Plays, Listeners, etc.
        """
        logger.info("📊 Parsing CSV 'Songs Performance'...")
        
        df.columns = df.columns.str.strip().str.lower()
        
        # Mapping des colonnes
        column_mapping = {
            'song': ['song title', 'song', 'title', 'track'],
            'album': ['album', 'album name'],
            'plays': ['plays', 'play count'],
            'listeners': ['listeners', 'unique listeners']
        }
        
        actual_columns = {}
        for target, possibilities in column_mapping.items():
            for col in df.columns:
                if any(p in col for p in possibilities):
                    actual_columns[target] = col
                    break
        
        logger.info(f"   Colonnes détectées: {actual_columns}")
        
        data = []
        for _, row in df.iterrows():
            try:
                def clean_number(value):
                    if pd.isna(value):
                        return 0
                    if isinstance(value, str):
                        value = value.replace(',', '').replace(' ', '').strip()
                    try:
                        return int(float(value))
                    except:
                        return 0
                
                record = {
                    'song_name': row.get(actual_columns.get('song', df.columns[0]), 'Unknown'),
                    'album_name': row.get(actual_columns.get('album'), None),
                    'plays': clean_number(row.get(actual_columns.get('plays', df.columns[1]), 0)),
                    'listeners': clean_number(row.get(actual_columns.get('listeners'), 0)),
                    'collected_at': datetime.now()
                }
                
                data.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing ligne: {e}")
                continue
        
        logger.info(f"✅ {len(data)} chansons parsées")
        return data
    
    def parse_daily_plays(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV de plays quotidiens.
        
        Format: Date, Song, Plays
        """
        logger.info("📊 Parsing CSV 'Daily Plays'...")
        
        df.columns = df.columns.str.strip().str.lower()
        
        column_mapping = {
            'date': ['date', 'day'],
            'song': ['song', 'song title', 'title'],
            'plays': ['plays', 'play count']
        }
        
        actual_columns = {}
        for target, possibilities in column_mapping.items():
            for col in df.columns:
                if any(p in col for p in possibilities):
                    actual_columns[target] = col
                    break
        
        logger.info(f"   Colonnes détectées: {actual_columns}")
        
        data = []
        for _, row in df.iterrows():
            try:
                plays_val = row.get(actual_columns.get('plays', df.columns[2]), 0)
                if isinstance(plays_val, str):
                    plays_val = plays_val.replace(',', '').replace(' ', '')
                plays = int(float(plays_val)) if plays_val else 0
                
                date_str = row.get(actual_columns.get('date', df.columns[0]))
                date = pd.to_datetime(date_str).date()
                
                record = {
                    'song_name': row.get(actual_columns.get('song', df.columns[1]), 'Unknown'),
                    'date': date,
                    'plays': plays,
                    'collected_at': datetime.now()
                }
                
                data.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing ligne: {e}")
                continue
        
        logger.info(f"✅ {len(data)} enregistrements parsés")
        return data
    
    def parse_listeners(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV de listeners.
        
        Format: Date, Listeners
        """
        logger.info("📊 Parsing CSV 'Listeners'...")
        
        df.columns = df.columns.str.strip().str.lower()
        
        column_mapping = {
            'date': ['date', 'day'],
            'listeners': ['listeners', 'unique listeners']
        }
        
        actual_columns = {}
        for target, possibilities in column_mapping.items():
            for col in df.columns:
                if any(p in col for p in possibilities):
                    actual_columns[target] = col
                    break
        
        logger.info(f"   Colonnes détectées: {actual_columns}")
        
        data = []
        for _, row in df.iterrows():
            try:
                def clean_number(value):
                    if pd.isna(value):
                        return 0
                    if isinstance(value, str):
                        value = value.replace(',', '').replace(' ', '').strip()
                    try:
                        return int(float(value))
                    except:
                        return 0
                
                date_str = row.get(actual_columns.get('date', df.columns[0]))
                date = pd.to_datetime(date_str).date()
                
                record = {
                    'date': date,
                    'listeners': clean_number(row.get(actual_columns.get('listeners', df.columns[1]), 0)),
                    'collected_at': datetime.now()
                }
                
                data.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing ligne: {e}")
                continue
        
        logger.info(f"✅ {len(data)} jours parsés")
        return data
    
    def parse_csv_file(self, file_path: Path) -> Dict:
        """
        Parse un fichier CSV Apple Music.
        
        Args:
            file_path: Chemin vers le CSV
            
        Returns:
            Dict avec 'type' et 'data'
        """
        logger.info(f"\n📄 Lecture du fichier: {file_path.name}")
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            df = df.dropna(how='all')
            
            logger.info(f"   📊 {len(df)} lignes, {len(df.columns)} colonnes")
            
            csv_type = self.detect_csv_type(df)
            
            if not csv_type:
                logger.error("❌ Type de CSV non reconnu")
                return {'type': None, 'data': []}
            
            logger.info(f"   🏷️ Type détecté: {csv_type}")
            
            if csv_type == 'songs_performance':
                data = self.parse_songs_performance(df)
            elif csv_type == 'daily_plays':
                data = self.parse_daily_plays(df)
            elif csv_type == 'listeners':
                data = self.parse_listeners(df)
            else:
                logger.error(f"❌ Type '{csv_type}' non supporté")
                return {'type': None, 'data': []}
            
            return {
                'type': csv_type,
                'data': data,
                'source_file': file_path.name
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur parsing CSV: {e}")
            return {'type': None, 'data': []}


# Test
if __name__ == "__main__":
    parser = AppleMusicCSVParser()
    
    test_file = Path("data/raw/apple_music").glob("*.csv")
    for csv_file in test_file:
        result = parser.parse_csv_file(csv_file)
        print(f"\n✅ Type: {result['type']}")
        print(f"✅ Données: {len(result['data'])} enregistrements")
        if result['data']:
            print(f"✅ Exemple: {result['data'][0]}")
        break