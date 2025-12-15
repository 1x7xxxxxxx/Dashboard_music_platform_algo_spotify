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
        
        if not os.path.exists(RAW_DIR): return

        files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.xlsx', '.csv'))]
        if not files: 
            # print("⚠️ Aucun fichier.") # Commenté pour éviter le spam si vide
            return

        for file in files:
            file_path = RAW_DIR / file
            print(f"👉 Traitement de : {file}")

            try:
                result = self.parser.parse_csv(file_path)
                ftype = result['type']
                data = result['data']
                
                if result['type'] == 'error':
                    print(f"❌ ERREUR DE PARSING sur {file}. Vérifiez le format.")
                    continue

                if not data:
                    print(f"⚠️ Fichier vide ou illisible.")
                    continue

                count = 0
                
                # ==========================================
                # ROUTAGE INTELLIGENT (PERF vs ENGAGEMENT)
                # ==========================================
                
                # --- A. PERFORMANCES ---
                if ftype == 'performance_global': count = self.upsert_performance_global(data)
                elif ftype == 'performance_day': count = self.upsert_performance_day(data)
                elif ftype == 'performance_age': count = self.upsert_performance_age(data)
                elif ftype == 'performance_country': count = self.upsert_performance_country(data)
                elif ftype == 'performance_placement': count = self.upsert_performance_placement(data)
                
                # --- B. ENGAGEMENT (NOUVEAU) ---
                elif ftype == 'engagement_global': count = self.upsert_engagement_global(data)
                elif ftype == 'engagement_day': count = self.upsert_engagement_day(data)
                elif ftype == 'engagement_age': count = self.upsert_engagement_age(data)
                elif ftype == 'engagement_country': count = self.upsert_engagement_country(data)
                elif ftype == 'engagement_placement': count = self.upsert_engagement_placement(data)
                
                print(f"   ✅ {count} lignes insérées ({ftype})")
                self.archive_file(file)

            except Exception as e:
                print(f"   ❌ Erreur critique sur {file}: {e}")

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

    # =========================================================================
    # 1. UPSERTS PERFORMANCE (L'existant qui fonctionnait)
    # =========================================================================

    def upsert_performance_global(self, data):
        """Table: meta_insights_performance"""
        query = """
            INSERT INTO meta_insights_performance (
                campaign_name, spend, impressions, reach, frequency, results, cpr, 
                cpm, link_clicks, cpc, ctr, lp_views
            ) VALUES (
                %(campaign_name)s, %(spend)s, %(impressions)s, %(reach)s, %(frequency)s, %(results)s, %(cpr)s,
                %(cpm)s, %(link_clicks)s, %(cpc)s, %(ctr)s, %(lp_views)s
            )
            ON CONFLICT (campaign_name, date_start) DO UPDATE SET
                spend = EXCLUDED.spend, results = EXCLUDED.results,
                impressions = EXCLUDED.impressions, reach = EXCLUDED.reach,
                frequency = EXCLUDED.frequency, cpm = EXCLUDED.cpm,
                link_clicks = EXCLUDED.link_clicks, cpc = EXCLUDED.cpc,
                ctr = EXCLUDED.ctr, lp_views = EXCLUDED.lp_views,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_performance_day(self, data):
        """Table: meta_insights_performance_day"""
        query = """
            INSERT INTO meta_insights_performance_day (
                campaign_name, day_date, spend, results, cpr, impressions, reach
            ) VALUES (
                %(campaign_name)s, %(day_date)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s
            )
            ON CONFLICT (campaign_name, day_date) DO UPDATE SET
                spend = EXCLUDED.spend, results = EXCLUDED.results,
                cpr = EXCLUDED.cpr, impressions = EXCLUDED.impressions,
                reach = EXCLUDED.reach, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_performance_age(self, data):
        """Table: meta_insights_performance_age"""
        query = """
            INSERT INTO meta_insights_performance_age (
                campaign_name, age_range, spend, results, cpr, impressions, reach
            ) VALUES (
                %(campaign_name)s, %(age_range)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s
            )
            ON CONFLICT (campaign_name, age_range) DO UPDATE SET
                spend = EXCLUDED.spend, results = EXCLUDED.results,
                cpr = EXCLUDED.cpr, impressions = EXCLUDED.impressions,
                reach = EXCLUDED.reach, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_performance_country(self, data):
        """Table: meta_insights_performance_country"""
        query = """
            INSERT INTO meta_insights_performance_country (
                campaign_name, country, spend, results, cpr, impressions, reach
            ) VALUES (
                %(campaign_name)s, %(country)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s
            )
            ON CONFLICT (campaign_name, country) DO UPDATE SET
                spend = EXCLUDED.spend, results = EXCLUDED.results,
                cpr = EXCLUDED.cpr, impressions = EXCLUDED.impressions,
                reach = EXCLUDED.reach, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_performance_placement(self, data):
        """Table: meta_insights_performance_placement"""
        query = """
            INSERT INTO meta_insights_performance_placement (
                campaign_name, platform, placement, spend, results, cpr, impressions, reach
            ) VALUES (
                %(campaign_name)s, %(platform)s, %(placement)s, %(spend)s, %(results)s, %(cpr)s, %(impressions)s, %(reach)s
            )
            ON CONFLICT (campaign_name, platform, placement) DO UPDATE SET
                spend = EXCLUDED.spend, results = EXCLUDED.results,
                cpr = EXCLUDED.cpr, impressions = EXCLUDED.impressions,
                reach = EXCLUDED.reach, collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    # =========================================================================
    # 2. UPSERTS ENGAGEMENT (Les ajouts)
    # =========================================================================

    def upsert_engagement_global(self, data):
        """Table: meta_insights_engagement"""
        query = """
            INSERT INTO meta_insights_engagement (
                campaign_name, page_interactions, post_reactions, comments, saves, shares, link_clicks, post_likes
            ) VALUES (
                %(campaign_name)s, %(page_interactions)s, %(post_reactions)s, %(comments)s, %(saves)s, %(shares)s, %(link_clicks)s, %(post_likes)s
            )
            ON CONFLICT (campaign_name, date_start) DO UPDATE SET
                page_interactions = EXCLUDED.page_interactions, post_reactions = EXCLUDED.post_reactions,
                comments = EXCLUDED.comments, saves = EXCLUDED.saves, shares = EXCLUDED.shares,
                link_clicks = EXCLUDED.link_clicks, post_likes = EXCLUDED.post_likes,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_engagement_day(self, data):
        """Table: meta_insights_engagement_day"""
        query = """
            INSERT INTO meta_insights_engagement_day (
                campaign_name, day_date, page_interactions, post_reactions, comments, saves, shares, link_clicks, post_likes
            ) VALUES (
                %(campaign_name)s, %(day_date)s, %(page_interactions)s, %(post_reactions)s, %(comments)s, %(saves)s, %(shares)s, %(link_clicks)s, %(post_likes)s
            )
            ON CONFLICT (campaign_name, day_date) DO UPDATE SET
                page_interactions = EXCLUDED.page_interactions, post_reactions = EXCLUDED.post_reactions,
                comments = EXCLUDED.comments, saves = EXCLUDED.saves, shares = EXCLUDED.shares,
                link_clicks = EXCLUDED.link_clicks, post_likes = EXCLUDED.post_likes,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_engagement_age(self, data):
        """Table: meta_insights_engagement_age"""
        query = """
            INSERT INTO meta_insights_engagement_age (
                campaign_name, age_range, page_interactions, post_reactions, comments, saves, shares, link_clicks, post_likes
            ) VALUES (
                %(campaign_name)s, %(age_range)s, %(page_interactions)s, %(post_reactions)s, %(comments)s, %(saves)s, %(shares)s, %(link_clicks)s, %(post_likes)s
            )
            ON CONFLICT (campaign_name, age_range) DO UPDATE SET
                page_interactions = EXCLUDED.page_interactions, post_reactions = EXCLUDED.post_reactions,
                comments = EXCLUDED.comments, saves = EXCLUDED.saves, shares = EXCLUDED.shares,
                link_clicks = EXCLUDED.link_clicks, post_likes = EXCLUDED.post_likes,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_engagement_country(self, data):
        """Table: meta_insights_engagement_country"""
        query = """
            INSERT INTO meta_insights_engagement_country (
                campaign_name, country, page_interactions, post_reactions, comments, saves, shares, link_clicks, post_likes
            ) VALUES (
                %(campaign_name)s, %(country)s, %(page_interactions)s, %(post_reactions)s, %(comments)s, %(saves)s, %(shares)s, %(link_clicks)s, %(post_likes)s
            )
            ON CONFLICT (campaign_name, country) DO UPDATE SET
                page_interactions = EXCLUDED.page_interactions, post_reactions = EXCLUDED.post_reactions,
                comments = EXCLUDED.comments, saves = EXCLUDED.saves, shares = EXCLUDED.shares,
                link_clicks = EXCLUDED.link_clicks, post_likes = EXCLUDED.post_likes,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def upsert_engagement_placement(self, data):
        """Table: meta_insights_engagement_placement"""
        query = """
            INSERT INTO meta_insights_engagement_placement (
                campaign_name, platform, placement, page_interactions, post_reactions, comments, saves, shares, link_clicks, post_likes
            ) VALUES (
                %(campaign_name)s, %(platform)s, %(placement)s, %(page_interactions)s, %(post_reactions)s, %(comments)s, %(saves)s, %(shares)s, %(link_clicks)s, %(post_likes)s
            )
            ON CONFLICT (campaign_name, platform, placement) DO UPDATE SET
                page_interactions = EXCLUDED.page_interactions, post_reactions = EXCLUDED.post_reactions,
                comments = EXCLUDED.comments, saves = EXCLUDED.saves, shares = EXCLUDED.shares,
                link_clicks = EXCLUDED.link_clicks, post_likes = EXCLUDED.post_likes,
                collected_at = CURRENT_TIMESTAMP;
        """
        return self._execute_upsert(query, data)

    def archive_file(self, filename):
        src = RAW_DIR / filename
        
        # Nettoyage des préfixes multiples
        clean_name = re.sub(r'(processed_\d{8}_\d{6}_)+', '', filename)
        
        # Ajout timestamp unique
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_name = f"processed_{ts}_{clean_name}"
        
        dst = ARCHIVE_DIR / new_name
        
        try:
            shutil.move(str(src), str(dst))
            print(f"   📦 Fichier archivé : {new_name}")
        except Exception as e:
            print(f"⚠️ Erreur archivage: {e}")

if __name__ == "__main__":
    watcher = MetaAdsWatcher()
    watcher.process_files()