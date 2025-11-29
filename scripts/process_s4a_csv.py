#Intérêt du fichier :
# Tester localement : Vérifier que ton parser fonctionne sur un nouveau type de fichier CSV sans devoir attendre que le DAG se déclenche (15 min).

#Reprise sur erreur (Backfill) : Si ton Airflow plante ou si tu as 50 fichiers d'historique à charger d'un coup depuis ton PC, ce script est plus rapide et direct.

#Debug : Il affiche les logs directement dans ta console, ce qui est plus pratique pour voir pourquoi un fichier est rejeté.

"""Script de traitement manuel des CSV Spotify for Artists."""
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Ajout du chemin racine pour les imports
# On s'assure que Python trouve le dossier 'src' qu'on soit dans 'scripts' ou à la racine
# AJUSTEMENT DU CHEMIN (Pour trouver 'src' depuis le dossier 'scripts')
# On remonte de 2 niveaux : scripts/ -> racine/
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

# Imports du projet
try:
    from src.transformers.s4a_csv_parser import S4ACSVParser
    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    print(f"   Chemin actuel : {sys.path}")
    sys.exit(1)

# Config logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_s4a_csvs():
    print("\n" + "="*70)
    print("🎵 TRAITEMENT MANUEL CSV SPOTIFY FOR ARTISTS")
    print("="*70 + "\n")
    
    # 1. Vérification des dossiers
    raw_dir = project_root / 'data' / 'raw' / 'spotify_for_artists'
    processed_dir = project_root / 'data' / 'processed' / 'spotify_for_artists'
    
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    csv_files = list(raw_dir.glob('*.csv'))
    
    if not csv_files:
        print(f"⚠️  Dossier vide : {raw_dir}")
        print("👉 Ajoutez vos fichiers CSV ici et relancez.")
        return

    print(f"📊 {len(csv_files)} fichier(s) trouvé(s) dans {raw_dir.name}")

    # 2. Connexion BDD
    try:
        config = config_loader.load()
        db = PostgresHandler(**config['database'])
        print("✅ Connexion BDD réussie")
    except Exception as e:
        print(f"❌ Erreur connexion BDD : {e}")
        return

    parser = S4ACSVParser()
    processed_count = 0

    # 3. Traitement
    for csv_file in csv_files:
        print(f"\n📄 Analyse : {csv_file.name}")
        
        try:
            # Parsing
            result = parser.parse_csv_file(csv_file)
            csv_type = result.get('type')
            data = result.get('data')

            if not csv_type:
                print("   ⚠️  Type de CSV non reconnu (Colonnes inconnues ?)")
                continue

            print(f"   🏷️  Type détecté : {csv_type}")
            print(f"   📊 {len(data)} lignes extraites")

            # Ingestion
            if csv_type == 'songs_global':
                count = db.upsert_many(
                    table='s4a_songs_global',
                    data=data,
                    conflict_columns=['song'],
                    update_columns=['listeners', 'streams', 'saves', 'release_date', 'collected_at']
                )
                print(f"   ✅ {count} chansons mises à jour (Global)")

            elif csv_type == 'song_timeline':
                count = db.upsert_many(
                    table='s4a_song_timeline',
                    data=data,
                    conflict_columns=['song', 'date'],
                    update_columns=['streams', 'collected_at']
                )
                print(f"   ✅ {count} lignes de timeline insérées")

            elif csv_type == 'audience':
                count = db.upsert_many(
                    table='s4a_audience',
                    data=data,
                    conflict_columns=['date'],
                    update_columns=['listeners', 'streams', 'followers', 'collected_at']
                )
                print(f"   ✅ {count} jours d'audience insérés")

            # Archivage
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f"{csv_file.stem}_{timestamp}{csv_file.suffix}"
            archive_path = processed_dir / new_name
            csv_file.rename(archive_path)
            print(f"   📦 Archivé vers processed/")
            processed_count += 1

        except Exception as e:
            print(f"   ❌ Erreur : {e}")

    db.close()
    print(f"\n🏁 Terminé : {processed_count}/{len(csv_files)} fichiers traités.")

if __name__ == "__main__":
    process_s4a_csvs()