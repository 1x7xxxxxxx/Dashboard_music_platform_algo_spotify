import os
import sys
import shutil
import re  # Ajout pour nettoyer le nom
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler

try:
    from src.transformers.meta_insight_csv_parser import MetaInsightParser
except ImportError:
    sys.path.append(str(project_root / "src" / "transformers"))
    from meta_insight_csv_parser import MetaInsightParser

load_dotenv()

RAW_DIR = project_root / "data" / "raw" / "meta_ads" / "insights"
ARCHIVE_DIR = project_root / "data" / "processed" / "meta_ads" / "insights"

class MetaAdsWatcher:
    def __init__(self):
        self.db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT')),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        self.parser = MetaInsightParser()
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    def process_files(self):
        print(f"📂 Analyse Meta Ads dans : {RAW_DIR}")
        
        if not os.path.exists(RAW_DIR):
            print(f"❌ Dossier introuvable : {RAW_DIR}")
            return

        files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.xlsx', '.csv'))]
        
        if not files:
            print("⚠️ Aucun fichier Insights trouvé.")
            return

        for file in files:
            file_path = RAW_DIR / file
            print(f"👉 Traitement de : {file}")

            try:
                result = self.parser.parse_csv(file_path)
                ftype = result['type']
                data = result['data']
                
                # --- MODIFICATION CRITIQUE ICI ---
                if ftype == 'error':
                    print(f"❌ ERREUR DE PARSING sur {file}. Vérifiez openpyxl dans Docker.")
                    # On ne bouge PAS le fichier pour qu'il reste visible en erreur
                    continue 
                
                if not data:
                    print(f"⚠️ Fichier vide ou illisible : {file}")
                    # On ne bouge PAS le fichier
                    continue

                print(f"   🔍 Type : {ftype} | Lignes extraites : {len(data)}")

                count = 0
                if ftype == 'global_performance': count = self.upsert_performance(data)
                elif ftype == 'global_engagement': count = self.upsert_engagement(data)
                elif ftype == 'age': count = self.upsert_age(data)
                elif ftype == 'country': count = self.upsert_country(data)
                elif ftype == 'placement': count = self.upsert_placement(data)
                elif ftype == 'day': count = self.upsert_day(data)
                
                print(f"   ✅ {count} lignes insérées en base.")
                
                # On archive SEULEMENT si on a réussi à insérer
                self.archive_file(file)

            except Exception as e:
                print(f"   ❌ Erreur critique sur {file}: {e}")
        print(f"📂 Analyse Meta Ads dans : {RAW_DIR}")
        
        if not os.path.exists(RAW_DIR):
            print(f"❌ Dossier introuvable : {RAW_DIR}")
            return

        # On accepte xlsx et csv
        files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.xlsx', '.csv'))]
        
        if not files:
            print("⚠️ Aucun fichier Insights trouvé.")
            return

        for file in files:
            file_path = RAW_DIR / file
            print(f"👉 Traitement de : {file}")

            try:
                result = self.parser.parse_csv(file_path)
                ftype = result['type']
                data = result['data']
                
                if ftype == 'error' or not data:
                    print("   ⚠️ Fichier ignoré (vide ou type inconnu).")
                    self.archive_file(file)
                    continue
                
                print(f"   🔍 Type : {ftype} | Lignes extraites : {len(data)}")

                count = 0
                if ftype == 'global_performance': count = self.upsert_performance(data)
                elif ftype == 'global_engagement': count = self.upsert_engagement(data)
                elif ftype == 'age': count = self.upsert_age(data)
                elif ftype == 'country': count = self.upsert_country(data)
                elif ftype == 'placement': count = self.upsert_placement(data)
                elif ftype == 'day': count = self.upsert_day(data)
                
                print(f"   ✅ {count} lignes insérées en base.")
                self.archive_file(file)

            except Exception as e:
                print(f"   ❌ Erreur critique sur {file}: {e}")

    # --- SQL HELPER ---
    def _execute_upsert(self, query, data):
        if not data: return 0
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

    # --- UPSERT FUNCTIONS ---
    def upsert_performance(self, data):
        query = """
            INSERT INTO meta_insights_performance (
                campaign_name, spend, impressions, reach, frequency, results, cpr, 
                cpm, link_clicks, cpc, ctr, lp_views
            ) VALUES (
                %(campaign_name)s, %(spend)s, %(impressions)s, %(reach)s, %(frequency)s, %(results)s, %(cpr)s,
                %(cpm)s, %(link_clicks)s, %(cpc)s, %(ctr)s, %(lp_views)s
            )
            ON CONFLICT (campaign_name, date_start) DO UPDATE SET
                spend = EXCLUDED.spend,
                impressions = EXCLUDED.impressions,
                reach = EXCLUDED.reach,
                frequency = EXCLUDED.frequency,
                results = EXCLUDED.results,
                link_clicks = EXCLUDED.link_clicks,
                cpc = EXCLUDED.cpc,
                ctr = EXCLUDED.ctr,
                lp_views = EXCLUDED.lp_views,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_engagement(self, data):
        query = """
            INSERT INTO meta_insights_engagement (
                campaign_name, page_interactions, post_reactions, comments, saves, shares
            ) VALUES (
                %(campaign_name)s, %(page_interactions)s, %(post_reactions)s, %(comments)s, %(saves)s, %(shares)s
            )
            ON CONFLICT (campaign_name, date_start) DO UPDATE SET
                page_interactions = EXCLUDED.page_interactions,
                post_reactions = EXCLUDED.post_reactions,
                comments = EXCLUDED.comments,
                shares = EXCLUDED.shares,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_age(self, data):
        query = """
            INSERT INTO meta_insights_age (campaign_name, age_range, spend, results, cpr, impressions, reach, page_interactions)
            VALUES (%(campaign_name)s, %(age_range)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s, %(page_interactions)s)
            ON CONFLICT (campaign_name, age_range) DO UPDATE SET spend = EXCLUDED.spend, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_country(self, data):
        query = """
            INSERT INTO meta_insights_country (campaign_name, country, spend, results, cpr, impressions, reach)
            VALUES (%(campaign_name)s, %(country)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s)
            ON CONFLICT (campaign_name, country) DO UPDATE SET spend = EXCLUDED.spend, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_placement(self, data):
        query = """
            INSERT INTO meta_insights_placement (campaign_name, platform, placement, spend, results, cpr, impressions, reach)
            VALUES (%(campaign_name)s, %(platform)s, %(placement)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s)
            ON CONFLICT (campaign_name, platform, placement) DO UPDATE SET spend = EXCLUDED.spend, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_day(self, data):
        query = """
            INSERT INTO meta_insights_day (campaign_name, day_date, spend, results, cpr, impressions, reach)
            VALUES (%(campaign_name)s, %(day_date)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s)
            ON CONFLICT (campaign_name, day_date) DO UPDATE SET spend = EXCLUDED.spend, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def archive_file(self, filename):
        src = RAW_DIR / filename
        
        # 1. Nettoyage du nom de fichier : On retire TOUS les 'processed_YYYYMMDD_HHMMSS_' existants
        clean_name = re.sub(r'(processed_\d{8}_\d{6}_)+', '', filename)
        
        # 2. Ajout du nouveau timestamp unique
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_name = f"processed_{ts}_{clean_name}"
        
        dst = ARCHIVE_DIR / new_name
        
        try:
            shutil.move(str(src), str(dst))
            print(f"   📦 Fichier archivé sous : {new_name}")
        except Exception as e:
            print(f"⚠️ Erreur archivage: {e}")

if __name__ == "__main__":
    watcher = MetaAdsWatcher()
    watcher.process_files()