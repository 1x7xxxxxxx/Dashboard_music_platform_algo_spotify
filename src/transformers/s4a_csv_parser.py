"""Parser pour les CSV Spotify for Artists."""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class S4ACSVParser:
    """Parse les CSV de Spotify for Artists."""
    
    def __init__(self):
        """Initialise le parser."""
        pass
    
    def detect_csv_type(self, df: pd.DataFrame) -> Optional[str]:
        """
        Détecte le type de CSV (songs, audience, etc.).
        
        Args:
            df: DataFrame pandas
            
        Returns:
            Type de CSV ou None
        """
        columns = set(df.columns.str.lower().str.strip())
        
        # CSV "Titres" (Songs Global)
        if 'song' in columns or 'titre' in columns:
            return 'songs_global'
        
        # CSV "Timeline" (Daily streams par chanson)
        if 'date' in columns and ('streams' in columns or 'écoutes' in columns):
            if 'song' in columns or 'titre' in columns:
                return 'song_timeline'
            else:
                return 'audience'
        
        return None
    
    def parse_songs_global(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV de chansons globales.
        
        Format attendu: Song, Listeners, Streams, Saves, Release Date
        """
        logger.info("📊 Parsing CSV 'Songs Global'...")
        
        # Normaliser les noms de colonnes
        df.columns = df.columns.str.strip().str.lower()
        
        # Mapping des colonnes possibles
        column_mapping = {
            'song': ['song', 'titre', 'track', 'chanson'],
            'listeners': ['listeners', 'auditeurs', 'unique listeners'],
            'streams': ['streams', 'écoutes', 'plays'],
            'saves': ['saves', 'enregistrements', 'favorites'],
            'release_date': ['release date', 'date de sortie', 'release_date', 'released']
        }
        
        # Trouver les colonnes réelles
        actual_columns = {}
        for target, possibilities in column_mapping.items():
            for col in df.columns:
                if any(p in col for p in possibilities):
                    actual_columns[target] = col
                    break
        
        logger.info(f"   Colonnes détectées: {actual_columns}")
        
        # Extraire les données
        data = []
        for _, row in df.iterrows():
            try:
                # Nettoyer les valeurs numériques (supprimer virgules, espaces)
                def clean_number(value):
                    if pd.isna(value):
                        return 0
                    if isinstance(value, str):
                        value = value.replace(',', '').replace(' ', '').strip()
                    try:
                        return int(float(value))
                    except:
                        return 0
                
                # Nettoyer la date
                release_date = None
                if 'release_date' in actual_columns:
                    date_str = row.get(actual_columns['release_date'])
                    if pd.notna(date_str):
                        try:
                            release_date = pd.to_datetime(date_str).date()
                        except:
                            pass
                
                record = {
                    'song': row.get(actual_columns.get('song', df.columns[0]), 'Unknown'),
                    'listeners': clean_number(row.get(actual_columns.get('listeners', df.columns[1]), 0)),
                    'streams': clean_number(row.get(actual_columns.get('streams', df.columns[2]), 0)),
                    'saves': clean_number(row.get(actual_columns.get('saves', df.columns[3]), 0)),
                    'release_date': release_date,
                    'collected_at': datetime.now()
                }
                
                data.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing ligne: {e}")
                continue
        
        logger.info(f"✅ {len(data)} chansons parsées")
        return data
    
    def parse_song_timeline(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV de timeline par chanson.
        
        Format attendu: Song, Date, Streams
        """
        logger.info("📊 Parsing CSV 'Song Timeline'...")
        
        df.columns = df.columns.str.strip().str.lower()
        
        # Mapping des colonnes
        column_mapping = {
            'song': ['song', 'titre', 'track'],
            'date': ['date', 'day', 'jour'],
            'streams': ['streams', 'écoutes', 'plays']
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
                # Nettoyer streams
                streams_val = row.get(actual_columns.get('streams', df.columns[2]), 0)
                if isinstance(streams_val, str):
                    streams_val = streams_val.replace(',', '').replace(' ', '')
                streams = int(float(streams_val)) if streams_val else 0
                
                # Parser date
                date_str = row.get(actual_columns.get('date', df.columns[1]))
                date = pd.to_datetime(date_str).date()
                
                record = {
                    'song': row.get(actual_columns.get('song', df.columns[0]), 'Unknown'),
                    'date': date,
                    'streams': streams,
                    'collected_at': datetime.now()
                }
                
                data.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing ligne: {e}")
                continue
        
        logger.info(f"✅ {len(data)} enregistrements timeline parsés")
        return data
    
    def parse_audience(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV d'audience globale.
        
        Format attendu: Date, Listeners, Streams, Followers
        """
        logger.info("📊 Parsing CSV 'Audience'...")
        
        df.columns = df.columns.str.strip().str.lower()
        
        column_mapping = {
            'date': ['date', 'day', 'jour'],
            'listeners': ['listeners', 'auditeurs'],
            'streams': ['streams', 'écoutes'],
            'followers': ['followers', 'abonnés', 'suiveurs']
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
                    'streams': clean_number(row.get(actual_columns.get('streams', df.columns[2]), 0)),
                    'followers': clean_number(row.get(actual_columns.get('followers', df.columns[3]), 0)),
                    'collected_at': datetime.now()
                }
                
                data.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing ligne: {e}")
                continue
        
        logger.info(f"✅ {len(data)} jours d'audience parsés")
        return data
    
    def parse_csv_file(self, file_path: Path) -> Dict:
        """
        Parse un fichier CSV et retourne les données structurées.
        
        Args:
            file_path: Chemin vers le CSV
            
        Returns:
            Dict avec 'type' et 'data'
        """
        logger.info(f"\n📄 Lecture du fichier: {file_path.name}")
        
        try:
            # Lire le CSV
            df = pd.read_csv(file_path, encoding='utf-8')
            
            # Supprimer les lignes vides
            df = df.dropna(how='all')
            
            logger.info(f"   📊 {len(df)} lignes, {len(df.columns)} colonnes")
            logger.info(f"   📋 Colonnes: {', '.join(df.columns.tolist()[:5])}")
            
            # Détecter le type
            csv_type = self.detect_csv_type(df)
            
            if not csv_type:
                logger.error("❌ Type de CSV non reconnu")
                return {'type': None, 'data': []}
            
            logger.info(f"   🏷️ Type détecté: {csv_type}")
            
            # Parser selon le type
            if csv_type == 'songs_global':
                data = self.parse_songs_global(df)
            elif csv_type == 'song_timeline':
                data = self.parse_song_timeline(df)
            elif csv_type == 'audience':
                data = self.parse_audience(df)
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
    parser = S4ACSVParser()
    
    # Exemple de test si un fichier existe
    test_file = Path("data/raw/spotify_for_artists").glob("*.csv")
    for csv_file in test_file:
        result = parser.parse_csv_file(csv_file)
        print(f"\n✅ Type: {result['type']}")
        print(f"✅ Données: {len(result['data'])} enregistrements")
        if result['data']:
            print(f"✅ Exemple: {result['data'][0]}")
        break