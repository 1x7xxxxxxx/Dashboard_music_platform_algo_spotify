import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

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
        print("📂 Analyse du dossier data/raw...")
        
        files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.csv')]
        
        if not files:
            print("⚠️ Aucun fichier CSV à traiter.")
            return

        for file in files:
            file_path = RAW_DIR / file
            print(f"👉 Traitement de : {file}")

            try:
                # 1. Parsing
                result = self.parser.parse_csv_file(file_path)
                
                if not result or not result.get('data'):
                    print(f"   ⚠️ Fichier vide ou ignoré.")
                    self.archive_file(file)
                    continue

                # 2. Sauvegarde UPSERT (Mise à jour intelligente)
                if result['type'] == 'song_timeline':
                    count = self.save_timeline_upsert(result['data'])
                    print(f"   ✅ {count} lignes traitées pour '{result['data'][0]['song']}'")
                
                # 3. Archivage
                self.archive_file(file)

            except Exception as e:
                print(f"   ❌ Erreur critique sur {file}: {e}")

    def save_timeline_upsert(self, data):
        """Insère ou Met à jour les données (évite les doublons)."""
        if not data: return 0

        # La requête SQL qui gère les conflits
        query = """
            INSERT INTO s4a_song_timeline (song, date, streams, collected_at)
            VALUES (%(song)s, %(date)s, %(streams)s, CURRENT_TIMESTAMP)
            ON CONFLICT (song, date) 
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
            print(f"❌ Erreur SQL: {e}")
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
            print("   📦 Fichier archivé.")
        except Exception as e:
            print(f"   ⚠️ Erreur archivage: {e}")

if __name__ == "__main__":
    watcher = S4AWatcher()
    watcher.process_files()