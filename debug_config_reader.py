import os
import sys
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Ajout du chemin racine pour les imports src
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

try:
    from src.database.postgres_handler import PostgresHandler
    from src.transformers.meta_csv_parser import MetaCSVParser
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    print("👉 Assurez-vous d'être à la racine du projet.")
    sys.exit(1)

load_dotenv()

def debug_pipeline():
    print("\n🚀 DIAGNOSTIC COMPLET PIPELINE META CONFIG")
    print("==========================================")

    # 1. Test Connexion BDD
    print("\n1️⃣  TEST CONNEXION POSTGRES")
    try:
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT')),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        print("   ✅ Connexion réussie.")
    except Exception as e:
        print(f"   ❌ Échec connexion : {e}")
        return

    # 2. Inspection des Tables
    print("\n2️⃣  INSPECTION DES TABLES SQL")
    tables = ['meta_campaigns', 'meta_adsets', 'meta_ads']
    
    for table in tables:
        try:
            # Récupère les colonnes de la table
            query = f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}';
            """
            cols = db.fetch_query(query)
            if not cols:
                print(f"   ❌ Table '{table}' : INTROUVABLE !")
            else:
                col_names = [c[0] for c in cols]
                print(f"   ✅ Table '{table}' : OK ({len(cols)} colonnes)")
                print(f"      Colonnes : {', '.join(col_names)}")
        except Exception as e:
            print(f"   ⚠️ Erreur inspection '{table}' : {e}")

    # 3. Parsing du Fichier
    print("\n3️⃣  TEST PARSING FICHIER")
    raw_dir = project_root / "data" / "raw" / "meta_ads" / "configuration"
    if not raw_dir.exists():
        print(f"   ❌ Dossier introuvable : {raw_dir}")
        return

    files = list(raw_dir.glob("*.csv")) + list(raw_dir.glob("*.xlsx"))
    if not files:
        print(f"   ❌ Aucun fichier trouvé dans {raw_dir}")
        return

    target = files[0]
    print(f"   📄 Fichier : {target.name}")
    
    parser = MetaCSVParser()
    result = parser.parse(target)
    
    if not result['data']:
        print("   ❌ Parsing échoué : Aucune donnée extraite.")
        return

    data = result['data']
    camps = data.get('campaigns', [])
    sets = data.get('adsets', [])
    ads = data.get('ads', [])
    
    print(f"   📊 Données extraites : {len(camps)} Campagnes, {len(sets)} AdSets, {len(ads)} Ads")

    # 4. Test Insertion (Dry Run)
    print("\n4️⃣  TEST INSERTION SQL (1 Ligne)")
    
    if camps:
        first_camp = camps[0]
        print(f"   👉 Tentative insertion Campagne : {first_camp['campaign_id']} - {first_camp['name']}")
        
        query = """
            INSERT INTO meta_campaigns (campaign_id, name, status, objective, buying_type)
            VALUES (%(campaign_id)s, %(name)s, %(status)s, %(objective)s, %(buying_type)s)
            ON CONFLICT (campaign_id) DO UPDATE SET
                name = EXCLUDED.name,
                updated_at = CURRENT_TIMESTAMP
            RETURNING campaign_id;
        """
        try:
            with db.conn.cursor() as cur:
                cur.execute(query, first_camp)
                res = cur.fetchone()
                db.conn.commit() # On valide pour voir si ça tient
                print(f"   ✅ SUCCÈS ! ID inséré/mis à jour : {res[0]}")
        except Exception as e:
            print(f"   ❌ ÉCHEC INSERTION SQL : {e}")
            db.conn.rollback()
    else:
        print("   ⚠️ Pas de campagne à tester.")

if __name__ == "__main__":
    debug_pipeline()