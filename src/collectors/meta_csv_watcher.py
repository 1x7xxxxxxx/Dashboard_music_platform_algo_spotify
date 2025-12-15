import os
import sys
import shutil
import re
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

RAW_DIR = project_root / "data" / "raw" / "meta_ads" / "configuration"
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
        print(f"📂 Analyse Config Meta dans : {RAW_DIR}")
        if not os.path.exists(RAW_DIR): return

        files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.xlsx', '.csv'))]
        if not files: return

        for file in files:
            file_path = RAW_DIR / file
            try:
                result = self.parser.parse(file_path)
                if not result or not result['data']: continue

                data = result['data']
                total = len(data['campaigns']) + len(data['adsets']) + len(data['ads'])
                if total == 0:
                    print("⚠️ 0 données trouvées.")
                    continue

                # Insertion dans l'ordre (Campagne -> AdSet -> Ad)
                c_count = self.upsert_campaigns(data['campaigns'])
                as_count = self.upsert_adsets(data['adsets'])
                ad_count = self.upsert_ads(data['ads'])

                print(f"   ✅ BDD : {c_count} Camps | {as_count} Sets | {ad_count} Ads")
                self.archive_file(file)

            except Exception as e:
                print(f"❌ CRASH sur {file}: {e}")

    # ==========================
    # UPSERTS COMPLETS
    # ==========================

    def upsert_campaigns(self, data):
        if not data: return 0
        query = """
            INSERT INTO meta_campaigns (campaign_id, campaign_name, start_time)
            VALUES (%(campaign_id)s, %(campaign_name)s, %(start_time)s)
            ON CONFLICT (campaign_id) DO UPDATE SET
                campaign_name = EXCLUDED.campaign_name,
                start_time = EXCLUDED.start_time,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute(query, data)

    def upsert_adsets(self, data):
        if not data: return 0
        query = """
            INSERT INTO meta_adsets (
                adset_id, campaign_id, adset_name, status, start_time,
                countries, cities, gender, age_min, age_max,
                flexible_inclusions, advantage_audience, age_range, targeting_optimization,
                publisher_platforms, instagram_positions, device_platforms
            )
            VALUES (
                %(adset_id)s, %(campaign_id)s, %(adset_name)s, %(status)s, %(start_time)s,
                %(countries)s, %(cities)s, %(gender)s, %(age_min)s, %(age_max)s,
                %(flexible_inclusions)s, %(advantage_audience)s, %(age_range)s, %(targeting_optimization)s,
                %(publisher_platforms)s, %(instagram_positions)s, %(device_platforms)s
            )
            ON CONFLICT (adset_id) DO UPDATE SET
                adset_name = EXCLUDED.adset_name,
                status = EXCLUDED.status,
                countries = EXCLUDED.countries,
                cities = EXCLUDED.cities,
                flexible_inclusions = EXCLUDED.flexible_inclusions,
                instagram_positions = EXCLUDED.instagram_positions,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute(query, data)

    def upsert_ads(self, data):
        if not data: return 0
        query = """
            INSERT INTO meta_ads (
                ad_id, adset_id, campaign_id, ad_name,
                title, body, video_file_name, call_to_action
            )
            VALUES (
                %(ad_id)s, %(adset_id)s, %(campaign_id)s, %(ad_name)s,
                %(title)s, %(body)s, %(video_file_name)s, %(call_to_action)s
            )
            ON CONFLICT (ad_id) DO UPDATE SET
                ad_name = EXCLUDED.ad_name,
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                video_file_name = EXCLUDED.video_file_name,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute(query, data)

    def _execute(self, query, data):
        count = 0
        try:
            with self.db.conn.cursor() as cur:
                for row in data:
                    cur.execute(query, row)
                    count += 1
                self.db.conn.commit()
        except Exception as e:
            print(f"⚠️ Erreur SQL : {e}")
            self.db.conn.rollback()
        return count

    def archive_file(self, filename):
        src = RAW_DIR / filename
        clean_name = re.sub(r'(processed_(config_)?\d{8}_\d{6}_)+', '', filename)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_name = f"processed_config_{ts}_{clean_name}"
        dst = ARCHIVE_DIR / new_name
        try: shutil.move(str(src), str(dst))
        except: pass

if __name__ == "__main__":
    watcher = MetaCSVWatcher()
    watcher.process_files()