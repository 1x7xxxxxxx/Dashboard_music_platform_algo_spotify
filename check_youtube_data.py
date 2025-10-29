"""Vérification des données YouTube après collecte."""
import sys
sys.path.insert(0, '.')

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

print("\n" + "="*70)
print("📊 VÉRIFICATION DONNÉES YOUTUBE")
print("="*70 + "\n")

config = config_loader.load()
db = PostgresHandler(**config['database'])

tables = {
    'youtube_channels': 'Chaînes',
    'youtube_channel_history': 'Historique chaîne',
    'youtube_videos': 'Vidéos',
    'youtube_video_stats': 'Stats vidéos',
    'youtube_playlists': 'Playlists',
    'youtube_comments': 'Commentaires'
}

total_records = 0

for table, label in tables.items():
    count = db.get_table_count(table)
    total_records += count
    
    status = "✅" if count > 0 else "⚠️ "
    print(f"{status} {label:20} : {count:>5} enregistrement(s)")
    
    # Afficher un échantillon si données présentes
    if count > 0 and table == 'youtube_channels':
        sample_query = f"SELECT channel_name, subscriber_count, video_count FROM {table} LIMIT 1"
        result = db.fetch_query(sample_query)
        
        if result:
            channel_name, subs, videos = result[0]
            print(f"   📺 Exemple: {channel_name} ({subs:,} abonnés, {videos} vidéos)")

db.close()

print("\n" + "="*70)

if total_records == 0:
    print("❌ AUCUNE DONNÉE COLLECTÉE")
    print("\n🔍 Actions à effectuer :")
    print("   1. Vérifier les credentials: python check_youtube_credentials.py")
    print("   2. Vérifier les logs Airflow")
    print("   3. Lancer manuellement le DAG youtube_daily")
else:
    print(f"✅ {total_records} ENREGISTREMENTS AU TOTAL")
    print("\n🎉 Données collectées avec succès !")
    print("   → Ouvrir le dashboard Streamlit")
    print("   → Aller sur la page YouTube")

print("="*70 + "\n")