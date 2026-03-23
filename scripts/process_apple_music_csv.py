import sys
import os
from pathlib import Path

# On remonte de 2 niveaux (scripts -> racine du projet) pour trouver 'src'
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Maintenant les imports fonctionneront
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

from src.transformers.apple_music_csv_parser import AppleMusicCSVParser

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def process_apple_music_csvs():
    """Traite tous les CSV Apple Music du dossier raw."""
    
    print("\n" + "="*70)
    print("🍎 TRAITEMENT CSV APPLE MUSIC")
    print("="*70 + "\n")
    
    # Dossiers
    raw_dir = Path('data/raw/apple_music')
    processed_dir = Path('data/processed/apple_music')
    
    # Créer les dossiers si nécessaire
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # Chercher les CSV
    csv_files = list(raw_dir.glob('*.csv'))
    
    if not csv_files:
        print(f"⚠️  Aucun fichier CSV trouvé dans {raw_dir}")
        print("\n💡 Pour ajouter des CSV :")
        print(f"   1. Exportez vos données depuis https://artists.apple.com")
        print(f"   2. Placez les fichiers .csv dans : {raw_dir}")
        print(f"   3. Relancez ce script\n")
        return
    
    print(f"📁 Dossier source : {raw_dir}")
    print(f"📊 {len(csv_files)} fichier(s) trouvé(s) :\n")
    
    for i, csv_file in enumerate(csv_files, 1):
        print(f"   {i}. {csv_file.name}")
    
    print("\n" + "-"*70)
    
    # Connexion DB
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # Parser
    parser = AppleMusicCSVParser()
    
    processed_count = 0
    total_records = 0
    
    # Traiter chaque fichier
    for csv_file in csv_files:
        print(f"\n📄 Traitement : {csv_file.name}")
        print("-" * 70)
        
        try:
            # Parser le CSV
            result = parser.parse_csv_file(csv_file)
            
            if not result['type']:
                print(f"   ⚠️  Type non reconnu - Fichier ignoré")
                continue
            
            if not result['data']:
                print(f"   ⚠️  Aucune donnée extraite - Fichier ignoré")
                continue
            
            csv_type = result['type']
            data = result['data']
            
            print(f"   🏷️  Type détecté : {csv_type}")
            print(f"   📊 {len(data)} enregistrement(s)")
            
            # Stocker selon le type
            if csv_type == 'songs_performance':
                # ✅ CORRECTION : Ajouter les nouvelles colonnes dans update_columns
                count = db.upsert_many(
                    table='apple_songs_performance',
                    data=data,
                    conflict_columns=['song_name'],
                    update_columns=[
                        'album_name', 'plays', 'listeners', 
                        'shazam_count', 'radio_spins', 'purchases',
                        'collected_at'
                    ]
                )
                print(f"   ✅ {count} chanson(s) stockée(s)")
            
            elif csv_type == 'daily_plays':
                count = db.upsert_many(
                    table='apple_daily_plays',
                    data=data,
                    conflict_columns=['song_name', 'date'],
                    update_columns=['plays', 'collected_at']
                )
                print(f"   ✅ {count} enregistrement(s) timeline stocké(s)")
            
            elif csv_type == 'listeners':
                count = db.upsert_many(
                    table='apple_listeners',
                    data=data,
                    conflict_columns=['date'],
                    update_columns=['listeners', 'collected_at']
                )
                print(f"   ✅ {count} jour(s) de listeners stocké(s)")
            
            else:
                print(f"   ❌ Type '{csv_type}' non supporté")
                continue
            
            total_records += len(data)
            
            # Archiver le fichier
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f"{csv_file.stem}_{timestamp}{csv_file.suffix}"
            archive_path = processed_dir / new_name
            
            csv_file.rename(archive_path)
            print(f"   📦 Archivé : {archive_path.name}")
            
            processed_count += 1
            
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            logger.error(f"Erreur détaillée pour {csv_file.name}:", exc_info=True)
            continue
    
    # Fermer la connexion
    db.close()
    
    # Résumé
    print("\n" + "="*70)
    print("✅ TRAITEMENT TERMINÉ")
    print("="*70)
    print(f"📊 Fichiers traités : {processed_count}/{len(csv_files)}")
    print(f"📊 Total enregistrements : {total_records}")
    print(f"📁 Archivés dans : {processed_dir}")
    print("="*70 + "\n")
    
    if processed_count > 0:
        print("🎉 Succès ! Les données sont maintenant disponibles dans PostgreSQL.")
        print("💡 Rafraîchissez votre dashboard pour voir les nouvelles données.\n")


if __name__ == "__main__":
    try:
        process_apple_music_csvs()
    except KeyboardInterrupt:
        print("\n\n⚠️  Traitement interrompu par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur fatale : {e}")
        logger.error("Erreur fatale:", exc_info=True)