"""Parser AMÉLIORÉ pour les CSV Apple Music for Artists avec support FR/EN."""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class AppleMusicCSVParser:
    """Parse les CSV d'Apple Music for Artists (FR et EN)."""
    
    def __init__(self):
        """Initialise le parser."""
        # Mapping FR/EN pour les colonnes
        self.column_mappings = {
            'song': [
                'morceau', 'song', 'song title', 'title', 'track', 'titre',
                'nom du morceau', 'nom de la chanson'
            ],
            'plays': [
                'écoutes', 'plays', 'play count', 'lectures', 'nombre d\'écoutes'
            ],
            'listeners': [
                'auditeurs', 'listeners', 'unique listeners', 'moy. d\'auditeurs',
                'moy. d\'auditeurs journalière', 'moyenne d\'auditeurs'
            ],
            'shazam': [
                'nombre de shazam', 'shazam', 'shazams', 'shazam count'
            ],
            'radio_spins': [
                'radio spins', 'spins', 'radio plays'
            ],
            'purchases': [
                'achats', 'purchases', 'buys', 'sales'
            ],
            'album': [
                'album', 'album name', 'nom de l\'album'
            ],
            'date': [
                'date', 'day', 'jour'
            ]
        }
    
    def find_column(self, df: pd.DataFrame, target: str) -> Optional[str]:
        """
        Trouve une colonne dans le DataFrame en utilisant le mapping.
        
        Args:
            df: DataFrame pandas
            target: Nom de la colonne cible ('song', 'plays', etc.)
            
        Returns:
            Nom de la colonne trouvée ou None
        """
        columns_lower = {col: col.lower().strip() for col in df.columns}
        
        for col_original, col_lower in columns_lower.items():
            for possibility in self.column_mappings.get(target, []):
                if possibility in col_lower or col_lower in possibility:
                    return col_original
        
        return None
    
    def detect_csv_type(self, df: pd.DataFrame) -> Optional[str]:
        """
        Détecte le type de CSV Apple Music.
        
        Args:
            df: DataFrame pandas
            
        Returns:
            Type de CSV ou None
        """
        # Vérifier si c'est un CSV de performance des chansons
        has_song = self.find_column(df, 'song') is not None
        has_plays = self.find_column(df, 'plays') is not None
        has_listeners = self.find_column(df, 'listeners') is not None
        has_date_real = any('date' in col.lower() or 'jour' in col.lower() 
                           for col in df.columns if 'auditeur' not in col.lower())
        
        # CSV de performance : chanson + plays + listeners (mais pas de date réelle)
        if has_song and has_plays and not has_date_real:
            return 'songs_performance'
        
        # CSV daily plays : date réelle + plays
        if has_date_real and has_plays:
            return 'daily_plays'
        
        # CSV listeners : date réelle + listeners
        if has_date_real and has_listeners:
            return 'listeners'
        
        return None
    
    def clean_number(self, value) -> int:
        """Nettoie et convertit une valeur en entier."""
        if pd.isna(value):
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            # Enlever les espaces, virgules, etc.
            value = value.replace(',', '').replace(' ', '').strip()
            try:
                return int(float(value))
            except:
                return 0
        return 0
    
    def parse_songs_performance(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV de performance des chansons.
        
        Format: Morceau, Écoutes, Auditeurs, Shazam, Radio Spins, Achats, etc.
        """
        logger.info("📊 Parsing CSV 'Songs Performance'...")
        
        # Trouver les colonnes
        song_col = self.find_column(df, 'song')
        plays_col = self.find_column(df, 'plays')
        listeners_col = self.find_column(df, 'listeners')
        album_col = self.find_column(df, 'album')
        shazam_col = self.find_column(df, 'shazam')
        radio_col = self.find_column(df, 'radio_spins')
        purchases_col = self.find_column(df, 'purchases')
        
        logger.info(f"   Colonnes détectées:")
        logger.info(f"      • Chanson: {song_col}")
        logger.info(f"      • Plays: {plays_col}")
        logger.info(f"      • Listeners: {listeners_col}")
        if album_col:
            logger.info(f"      • Album: {album_col}")
        if shazam_col:
            logger.info(f"      • Shazam: {shazam_col}")
        if radio_col:
            logger.info(f"      • Radio: {radio_col}")
        if purchases_col:
            logger.info(f"      • Achats: {purchases_col}")
        
        if not song_col or not plays_col:
            logger.error("❌ Colonnes essentielles manquantes")
            return []
        
        data = []
        for _, row in df.iterrows():
            try:
                record = {
                    'song_name': str(row[song_col]),
                    'album_name': str(row[album_col]) if album_col and not pd.isna(row[album_col]) else None,
                    'plays': self.clean_number(row[plays_col]),
                    'listeners': self.clean_number(row[listeners_col]) if listeners_col else 0,
                    'collected_at': datetime.now()
                }
                
                # Champs optionnels (si tables étendues)
                if shazam_col:
                    record['shazam_count'] = self.clean_number(row[shazam_col])
                if radio_col:
                    record['radio_spins'] = self.clean_number(row[radio_col])
                if purchases_col:
                    record['purchases'] = self.clean_number(row[purchases_col])
                
                data.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing ligne: {e}")
                continue
        
        logger.info(f"✅ {len(data)} chansons parsées")
        return data
    
    def parse_daily_plays(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse un CSV de plays quotidiens.
        
        Format: Date, Morceau, Écoutes
        """
        logger.info("📊 Parsing CSV 'Daily Plays'...")
        
        date_col = self.find_column(df, 'date')
        song_col = self.find_column(df, 'song')
        plays_col = self.find_column(df, 'plays')
        
        logger.info(f"   Colonnes détectées:")
        logger.info(f"      • Date: {date_col}")
        logger.info(f"      • Chanson: {song_col}")
        logger.info(f"      • Plays: {plays_col}")
        
        if not date_col or not plays_col:
            logger.error("❌ Colonnes essentielles manquantes")
            return []
        
        data = []
        for _, row in df.iterrows():
            try:
                date = pd.to_datetime(row[date_col]).date()
                
                record = {
                    'song_name': str(row[song_col]) if song_col else 'Unknown',
                    'date': date,
                    'plays': self.clean_number(row[plays_col]),
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
        
        Format: Date, Auditeurs
        """
        logger.info("📊 Parsing CSV 'Listeners'...")
        
        date_col = self.find_column(df, 'date')
        listeners_col = self.find_column(df, 'listeners')
        
        logger.info(f"   Colonnes détectées:")
        logger.info(f"      • Date: {date_col}")
        logger.info(f"      • Listeners: {listeners_col}")
        
        if not date_col or not listeners_col:
            logger.error("❌ Colonnes essentielles manquantes")
            return []
        
        data = []
        for _, row in df.iterrows():
            try:
                date = pd.to_datetime(row[date_col]).date()
                
                record = {
                    'date': date,
                    'listeners': self.clean_number(row[listeners_col]),
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
            # Essayer plusieurs encodages
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    logger.info(f"   ✅ Encodage détecté: {encoding}")
                    break
                except:
                    continue
            
            if df is None:
                logger.error("❌ Impossible de lire le CSV avec les encodages supportés")
                return {'type': None, 'data': []}
            
            df = df.dropna(how='all')
            
            logger.info(f"   📊 {len(df)} lignes, {len(df.columns)} colonnes")
            logger.info(f"   📋 Colonnes: {', '.join(df.columns)}")
            
            csv_type = self.detect_csv_type(df)
            
            if not csv_type:
                logger.error("❌ Type de CSV non reconnu")
                logger.error(f"   Colonnes disponibles: {list(df.columns)}")
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
            import traceback
            logger.error(traceback.format_exc())
            return {'type': None, 'data': []}


# Test
if __name__ == "__main__":
    parser = AppleMusicCSVParser()
    
    test_file = Path("/mnt/user-data/uploads/songs_1700256678_2015-06-30_2025-10-24.csv")
    
    if test_file.exists():
        print("\n" + "="*70)
        print("🧪 TEST DU PARSER APPLE MUSIC")
        print("="*70 + "\n")
        
        result = parser.parse_csv_file(test_file)
        
        print(f"\n✅ Type: {result['type']}")
        print(f"✅ Données: {len(result['data'])} enregistrements")
        
        if result['data']:
            print(f"\n📊 Premiers enregistrements:")
            for i, record in enumerate(result['data'][:3], 1):
                print(f"\n   {i}. {record}")
        
        print("\n" + "="*70)
        print("✅ TEST TERMINÉ")
        print("="*70 + "\n")
    else:
        print(f"❌ Fichier introuvable: {test_file}")