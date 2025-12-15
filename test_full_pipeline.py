import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Setup des chemins
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler
from src.collectors.meta_insight_watcher import MetaAdsWatcher

load_dotenv()

def test_pipeline():
    print("🚀 DÉMARRAGE DU TEST PIPELINE COMPLET (PAYS)")
    print("="*60)
    
    # 1. Vérification du fichier
    raw_dir = project_root / "data" / "raw" / "meta_ads" / "insights"
    files = list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.csv"))
    
    if not files:
        print(f"❌ Aucun fichier trouvé dans {raw_dir}")
        return

    target = files[0]
    print(f"📄 Fichier cible : {target.name}")

    # 2. Init Watcher
    try:
        watcher = MetaAdsWatcher()
        print("✅ Connexion BDD : OK")
    except Exception as e:
        print(f"❌ Erreur Connexion BDD : {e}")
        return

    # 3. Parsing
    print("\n--- ÉTAPE 1 : PARSING ---")
    result = watcher.parser.parse_csv(target)
    
    if result['type'] == 'error':
        print("❌ Échec du parsing.")
        return
    
    data = result['data']
    ftype = result['type']
    print(f"✅ Données extraites : {len(data)} lignes")
    print(f"🏷️ Type détecté : {ftype}")

    if len(data) == 0:
        print("⚠️ Aucune donnée à insérer.")
        return

    # 4. Insertion SQL
    print("\n--- ÉTAPE 2 : INSERTION SQL ---")
    count = 0
    try:
        # 👇 GESTION DU TYPE COUNTRY AJOUTÉE
        if ftype == 'country':
            count = watcher.upsert_country(data)
        
        elif ftype == 'global_performance':
            count = watcher.upsert_performance(data)
        elif ftype == 'global_engagement':
            count = watcher.upsert_engagement(data)
        elif ftype == 'age':
            count = watcher.upsert_age(data)
        elif ftype == 'placement':
            count = watcher.upsert_placement(data)
        elif ftype == 'day':
            count = watcher.upsert_day(data)
        else:
            print(f"⚠️ Type {ftype} non reconnu par le script de test.")
            return
            
        print(f"✅ SUCCÈS : {count} lignes insérées.")
    except Exception as e:
        print(f"❌ Erreur SQL durant l'insertion : {e}")
        return

    # 5. Vérification
    print("\n--- ÉTAPE 3 : VÉRIFICATION EN BASE ---")
    # Mapping simple pour trouver la table
    table_map = {
        'country': 'meta_insights_country',
        'age': 'meta_insights_age',
        'global_performance': 'meta_insights_performance'
    }
    table = table_map.get(ftype, f"meta_insights_{ftype}")
    
    try:
        res = watcher.db.fetch_query(f"SELECT COUNT(*) FROM {table}")
        print(f"📊 Lignes totales dans '{table}' : {res[0][0]}")
        
        # Aperçu
        cols = "campaign_name, country, spend" if ftype == 'country' else "*"
        last = watcher.db.fetch_query(f"SELECT {cols} FROM {table} ORDER BY collected_at DESC LIMIT 1")
        if last:
            print(f"🔎 Dernière entrée : {last[0]}")
            
    except Exception as e:
        print(f"⚠️ Impossible de vérifier la table : {e}")
    
    print("\n🎉 TEST TERMINÉ.")

if __name__ == "__main__":
    test_pipeline()