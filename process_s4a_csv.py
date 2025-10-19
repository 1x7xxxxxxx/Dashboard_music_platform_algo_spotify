"""Script pour traiter automatiquement les CSV Spotify for Artists."""
import sys
from pathlib import Path
from datetime import datetime
import shutil
import logging

sys.path.append(str(Path(__file__).parent))

from src.transformers.s4a_csv_parser import S4ACSVParser
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S4ACSVProcessor:
    """Processeur automatique de CSV S4A."""
    
    def __init__(self):
        """Initialise le processeur."""
        self.config = config_loader.load()
        self.db_config = self.config['database']
        
        self.raw_dir = Path("data/raw/spotify_for_artists")
        self.processed_dir = Path("data/processed/spotify_for_artists")
        
        # Créer les dossiers
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        self.parser = S4ACSVParser()
        
        # Connexion DB
        self.db = PostgresHandler(**self.db_config)
    
    def get_new_csv_files(self):
        """Récupère les nouveaux fichiers CSV à traiter."""
        csv_files = list(self.raw_dir.glob("*.csv"))
        logger.info(f"📁 {len(csv_files)} fichier(s) CSV trouvé(s) dans {self.raw_dir}")
        return csv_files
    
    def store_in_database(self, csv_type: str, data: list):
        """Stocke les données dans PostgreSQL."""
        if not data:
            logger.warning("⚠️ Aucune donnée à stocker")
            return 0
        
        logger.info(f"💾 Stockage dans PostgreSQL ({csv_type})...")
        
        try:
            if csv_type == 'songs_global':
                count = self.db.upsert_many(
                    table='s4a_songs_global',
                    data=data,
                    conflict_columns=['song'],
                    update_columns=['listeners', 'streams', 'saves', 'collected_at']
                )
            
            elif csv_type == 'song_timeline':
                count = self.db.upsert_many(
                    table='s4a_song_timeline',
                    data=data,
                    conflict_columns=['song', 'date'],
                    update_columns=['streams', 'collected_at']
                )
            
            elif csv_type == 'audience':
                count = self.db.upsert_many(
                    table='s4a_audience',
                    data=data,
                    conflict_columns=['date'],
                    update_columns=['listeners', 'streams', 'followers', 'collected_at']
                )
            
            else:
                logger.error(f"❌ Type '{csv_type}' non supporté pour le stockage")
                return 0
            
            logger.info(f"✅ {count} enregistrement(s) stocké(s)")
            return count
            
        except Exception as e:
            logger.error(f"❌ Erreur stockage: {e}")
            return 0
    
    def archive_file(self, file_path: Path):
        """Archive un fichier traité."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        archive_path = self.processed_dir / new_name
        
        try:
            shutil.move(str(file_path), str(archive_path))
            logger.info(f"📦 Archivé: {archive_path.name}")
        except Exception as e:
            logger.error(f"❌ Erreur archivage: {e}")
    
    def process_file(self, file_path: Path):
        """Traite un fichier CSV."""
        logger.info("\n" + "="*70)
        logger.info(f"🔄 TRAITEMENT: {file_path.name}")
        logger.info("="*70)
        
        try:
            # 1. Parser le CSV
            result = self.parser.parse_csv_file(file_path)
            
            if not result['type']:
                logger.error("❌ Type de CSV non reconnu, fichier ignoré")
                return False
            
            # 2. Stocker dans PostgreSQL
            count = self.store_in_database(result['type'], result['data'])
            
            if count > 0:
                # 3. Archiver le fichier
                self.archive_file(file_path)
                logger.info("✅ Fichier traité avec succès")
                return True
            else:
                logger.warning("⚠️ Aucune donnée stockée")
                return False
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement: {e}")
            return False
    
    def process_all(self):
        """Traite tous les nouveaux fichiers CSV."""
        logger.info("\n" + "="*70)
        logger.info("🚀 TRAITEMENT AUTOMATIQUE CSV SPOTIFY FOR ARTISTS")
        logger.info("="*70 + "\n")
        
        csv_files = self.get_new_csv_files()
        
        if not csv_files:
            logger.info("ℹ️ Aucun nouveau fichier CSV à traiter")
            logger.info(f"   Placez vos CSV dans: {self.raw_dir}")
            return
        
        success_count = 0
        for csv_file in csv_files:
            if self.process_file(csv_file):
                success_count += 1
        
        logger.info("\n" + "="*70)
        logger.info(f"✅ TRAITEMENT TERMINÉ: {success_count}/{len(csv_files)} fichier(s) traité(s)")
        logger.info("="*70 + "\n")
    
    def close(self):
        """Ferme les connexions."""
        self.db.close()


def main():
    """Point d'entrée principal."""
    processor = S4ACSVProcessor()
    
    try:
        processor.process_all()
    finally:
        processor.close()


if __name__ == "__main__":
    main()