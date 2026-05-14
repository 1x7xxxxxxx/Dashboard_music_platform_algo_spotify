import logging
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Setup chemin
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler
# Import du parser que l'on vient de créer
from src.collectors.s4a_csv_parser import S4ACSVParser

load_dotenv()

RAW_DIR = project_root / "data" / "raw"
ARCHIVE_DIR = project_root / "data" / "archive"

class S4AWatcher:
    def __init__(self):
        # Connexion BDD (via .env)
        self.db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT')),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        self.parser = S4ACSVParser()
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    def process_files(self):
        logger.info("Analyzing data/raw folder")
        
        files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.csv')]
        
        if not files:
            logger.warning("No CSV files to process")
            return

        for file in files:
            file_path = RAW_DIR / file
            logger.info(f"Processing {file}")

            try:
                # 1. Parsing
                result = self.parser.parse_csv_file(file_path)
                
                if not result or not result.get('data'):
                    logger.warning(f"Empty or skipped file: {file}")
                    self.archive_file(file)
                    continue

                # 2. Sauvegarde UPSERT (Mise à jour intelligente)
                if result['type'] == 'song_timeline':
                    count = self.save_timeline_upsert(result['data'])
                    logger.info(f"{count} rows processed for '{result['data'][0]['song']}'")
                
                # 3. Archivage
                self.archive_file(file)

            except Exception as e:
                logger.error(f"Critical error on {file}: {e}")

    def save_timeline_upsert(self, data):
        """Insère ou Met à jour les données (évite les doublons)."""
        if not data: return 0

        # La requête SQL qui gère les conflits
        query = """
            INSERT INTO s4a_song_timeline (artist_id, song, date, streams, collected_at)
            VALUES (1, %(song)s, %(date)s, %(streams)s, CURRENT_TIMESTAMP)
            ON CONFLICT (artist_id, song, date)
            DO UPDATE SET
                streams = EXCLUDED.streams,
                collected_at = CURRENT_TIMESTAMP;
        """
        
        count = 0
        try:
            with self.db.conn.cursor() as cur:
                for row in data:
                    cur.execute(query, row)
                    count += 1
                self.db.conn.commit()
        except Exception as e:
            logger.error(f"SQL error: {e}")
            self.db.conn.rollback()
        
        return count

    def archive_file(self, filename):
        """Déplace le fichier traité."""
        src = RAW_DIR / filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # On renomme pour garder une trace unique
        dst = ARCHIVE_DIR / f"processed_{timestamp}_{filename}"
        
        try:
            shutil.move(str(src), str(dst))
            logger.info("File archived")
        except Exception as e:
            logger.warning(f"Archive error: {e}")

if __name__ == "__main__":
    watcher = S4AWatcher()
    watcher.process_files()