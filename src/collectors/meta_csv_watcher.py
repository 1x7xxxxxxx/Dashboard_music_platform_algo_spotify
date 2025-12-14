import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler

try:
    from src.transformers.meta_csv_parser import MetaCSVParser
except ImportError:
    sys.path.append(str(project_root / "src" / "transformers"))
    from meta_csv_parser import MetaCSVParser

load_dotenv()

# 👇 AJUSTEZ CE CHEMIN RAW SI VOS CONFIGS SONT AILLEURS
RAW_DIR = project_root / "data" / "raw" / "meta_ads" / "configuration"

# 👇 NOUVEL EMPLACEMENT ARCHIVE CONFIG
ARCHIVE_DIR = project_root / "data" / "processed" / "meta_ads" / "configuration"

class MetaCSVWatcher: 
    def __init__(self):
        self.db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT')),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        self.parser = MetaCSVParser()
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    def process_files(self):
        print(f"📂 Analyse Meta Config dans : {RAW_DIR}")
        
        if not os.path.exists(RAW_DIR):
             print(f"❌ Dossier introuvable : {RAW_DIR}")
             return

        files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.csv')]
        
        if not files:
            print("⚠️ Aucun fichier CSV trouvé.")
            return

        for file in files:
            file_path = RAW_DIR / file
            
            try:
                result = self.parser.parse_csv(file_path)
                
                if not result or not result.get('data'):
                    continue
                
                print(f"👉 Traitement Config : {file}")
                self.save_campaigns(result['data'])
                print(f"   ✅ Campagnes mises à jour.")
                self.archive_file(file)

            except Exception as e:
                pass

    def save_campaigns(self, data):
        if not data: return
        query = """
            INSERT INTO meta_campaigns (campaign_id, campaign_name, status, start_time)
            VALUES (%(campaign_id)s, %(campaign_name)s, %(status)s, %(start_time)s)
            ON CONFLICT (campaign_id) DO UPDATE SET
                campaign_name = EXCLUDED.campaign_name,
                status = EXCLUDED.status,
                start_time = EXCLUDED.start_time;
        """
        try:
            with self.db.conn.cursor() as cur:
                for row in data:
                    cur.execute(query, row)
                self.db.conn.commit()
        except Exception as e:
            print(f"❌ Erreur SQL Config: {e}")
            self.db.conn.rollback()

    def archive_file(self, filename):
        src = RAW_DIR / filename
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = ARCHIVE_DIR / f"processed_config_{ts}_{filename}"
        try:
            shutil.move(str(src), str(dst))
            print(f"   📦 Fichier archivé dans : {ARCHIVE_DIR}")
        except: pass

if __name__ == "__main__":
    watcher = MetaCSVWatcher()
    watcher.process_files()