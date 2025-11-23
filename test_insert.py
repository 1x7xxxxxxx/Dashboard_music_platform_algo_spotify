import sys
import os
from datetime import datetime

# Ajout du path pour trouver tes modules src
sys.path.append(os.getcwd())

from src.database.postgres_handler import PostgresHandler

# Configuration pour LOCALHOST (Ton PC)
# Attention : On utilise le port 5433 (externe) et non 5432 (interne Docker)
DB_CONFIG = {
    "host": "localhost", 
    "port": 5433,
    "database": "spotify_etl",
    "user": "postgres",
    "password": "Wowow1357911!" 
}

def test_connection_and_insert():
    print(f"🔌 Tentative de connexion à {DB_CONFIG['database']} sur le port {DB_CONFIG['port']}...")
    
    try:
        db = PostgresHandler(**DB_CONFIG)
        
        # 1. Vérifier si la table existe
        if not db.table_exists('artists'):
            print("❌ La table 'artists' n'existe pas ! Lance init_db.sql.")
            return

        print("✅ Connexion réussie et table trouvée.")

        # 2. Tentative d'insertion d'un artiste bidon
        fake_artist = {
            'artist_id': 'TEST_DEBUG_001',
            'name': 'Test Debug Artist',
            'followers': 123,
            'popularity': 100,
            'genres': ['test'],
            'collected_at': datetime.now()
        }

        print("📝 Tentative d'insertion...")
        db.upsert_many(
            table='artists',
            data=[fake_artist],
            conflict_columns=['artist_id'],
            update_columns=['name', 'followers']
        )
        
        # 3. Vérification immédiate
        result = db.fetch_query("SELECT name FROM artists WHERE artist_id = 'TEST_DEBUG_001'")
        if result:
            print(f"🎉 SUCCÈS ! Donnée trouvée en base : {result[0][0]}")
        else:
            print("😱 ÉCHEC : L'insertion semble avoir fonctionné mais le SELECT ne renvoie rien.")

        db.close()

    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE : {e}")

if __name__ == "__main__":
    test_connection_and_insert()